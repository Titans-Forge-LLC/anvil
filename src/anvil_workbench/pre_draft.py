"""Capture and inspect a private, unapproved pre-draft Git handoff.

The file contains task and failure text. Keep it private. Stored text is
untrusted data, not authority, commands to run, or evidence of current success.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess

MAX_FILE = 16384
MAX_GIT = 2 * 1024 * 1024
MAX_PACKET = 256 * 1024


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def _canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode('ascii')


def _inside(root, name):
    path = (root / Path(name).expanduser()).resolve(strict=True)
    path.relative_to(root)
    if not path.is_file():
        raise ValueError('handoff input must be a regular file')
    return path


def _read(root, name):
    path = _inside(root, name)
    with path.open('rb') as stream:
        raw = stream.read(MAX_FILE + 1)
    if len(raw) > MAX_FILE:
        raise ValueError('handoff input exceeds 16 KiB')
    text = raw.decode('utf-8')
    if '\x00' in text:
        raise ValueError('handoff input contains NUL')
    return {'path': path.relative_to(root).as_posix(), 'sha256': _digest(raw), 'text': text}


def _git(root, *args, input_data=None):
    # Do not allow parent shell settings to redirect Git to another repository.
    env = os.environ.copy()
    for key in tuple(env):
        if key.startswith('GIT_'):
            env.pop(key)
    env.update(GIT_OPTIONAL_LOCKS='0', GIT_CONFIG_NOSYSTEM='1', LC_ALL='C')
    result = subprocess.run(['git', '-c', 'core.fsmonitor=false', *args], cwd=root,
                            input=input_data, capture_output=True, timeout=20, env=env)
    if result.returncode:
        raise ValueError('git inspection failed: ' + result.stderr.decode('utf-8', 'replace')[-1000:])
    if len(result.stdout) > MAX_GIT:
        raise ValueError('git state exceeds 2 MiB; handoff refused')
    return result.stdout


def _state(root):
    top = Path(os.fsdecode(_git(root, 'rev-parse', '--show-toplevel').strip())).resolve()
    if top != root:
        raise ValueError('project root must be the Git worktree root')
    head = _git(root, 'rev-parse', '--verify', 'HEAD').strip().decode('ascii')
    # Git can deliberately suppress worktree changes for these entries. A
    # status/diff snapshot alone would otherwise report an edited file as fresh.
    tracked = _git(root, 'ls-files', '-v', '-z')
    for record in tracked.split(b'\0'):
        if not record:
            continue
        if len(record) < 3 or record[1:2] != b' ':
            raise ValueError('unrecognized Git index record')
        flag = record[0]
        if flag == ord('S') or ord('a') <= flag <= ord('z'):
            raise ValueError('Git index hides worktree changes; handoff refused')
    # A superproject diff only says a submodule is dirty; it does not identify
    # the dirty contents, and Git configuration may hide them entirely.
    staged = _git(root, 'ls-files', '--stage', '-z')
    for record in staged.split(b'\0'):
        if not record:
            continue
        if b'\t' not in record:
            raise ValueError('unrecognized Git staged record')
        if record.startswith(b'160000 '):
            raise ValueError('Git submodules are not covered by handoff freshness; handoff refused')
    # Git may execute configured clean/process filters while computing diffs,
    # even with --no-ext-diff.  Resolve effective attributes for every tracked
    # path before status/diff; config and attribute files can still race this
    # point-in-time check, so callers must trust the repository environment.
    paths = _git(root, 'ls-files', '--cached', '-z')
    if paths:
        attributes = _git(root, 'check-attr', '-z', '--stdin', 'filter', input_data=paths)
        fields = attributes.split(b'\0')
        if fields[-1:] != [b''] or (len(fields) - 1) % 3:
            raise ValueError('unrecognized Git attribute output')
        for i in range(0, len(fields) - 1, 3):
            if fields[i + 1] != b'filter':
                raise ValueError('unexpected Git attribute')
            if fields[i + 2] not in (b'unspecified', b'unset'):
                raise ValueError('Git filters may execute commands; handoff refused')
    status = _git(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all')
    index = _git(root, 'diff', '--cached', '--no-ext-diff', '--no-textconv', '--binary')
    work = _git(root, 'diff', '--no-ext-diff', '--no-textconv', '--binary')
    # Porcelain -z records rename/copy's other name as a second NUL field.
    records = status.split(b'\0') if status else []
    entries, untracked = [], []
    i = 0
    while i < len(records) and records[i]:
        row = records[i]
        if len(row) < 4 or row[2:3] != b' ':
            raise ValueError('unrecognized Git status record')
        code = row[:2].decode('ascii')
        name = os.fsdecode(row[3:])
        item = {'status': code, 'path': name}
        i += 1
        if 'R' in code or 'C' in code:
            if i >= len(records) or not records[i]:
                raise ValueError('incomplete Git rename record')
            item['other_path'] = os.fsdecode(records[i]); i += 1
        if code == '??':
            if (root / name).is_symlink():
                raise ValueError('untracked symlink cannot be safely fingerprinted')
            path = _inside(root, name)
            if path.stat().st_size > MAX_FILE:
                raise ValueError('untracked file cannot be safely fingerprinted')
            with path.open('rb') as stream:
                data = stream.read(MAX_FILE + 1)
            if len(data) > MAX_FILE:
                raise ValueError('untracked file exceeds 16 KiB')
            untracked.append({'path': name, 'sha256': _digest(data)})
        entries.append(item)
        if len(entries) > 256:
            raise ValueError('Git state exceeds 256 changed files')
    return {'head': head, 'status': entries, 'index_diff_sha256': _digest(index),
            'work_diff_sha256': _digest(work), 'untracked': untracked}


def _hint(value):
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value.encode('utf-8')) > 2048:
        raise ValueError('continuation hints must contain 1..2048 UTF-8 bytes')
    if any(ord(c) < 32 or ord(c) == 127 or c in '\u2028\u2029' for c in value):
        raise ValueError('continuation hints must be single-line text without control characters')
    return value


def capture(project_root, task_file, evidence_files, output, *, failed_check=None, dead_end=None):
    root = Path(project_root).expanduser().resolve(strict=True)
    if not root.is_dir() or not 0 <= len(evidence_files) <= 4:
        raise ValueError('expected a project root and at most four evidence files')
    destination = Path(output).expanduser().absolute()
    parent = destination.parent.resolve(strict=True)
    if parent == root or root in parent.parents:
        raise ValueError('handoff output must be outside the project to avoid changing its Git state')
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('handoff output already exists')
    task = _read(root, task_file)
    if not task['text'].strip():
        raise ValueError('task must not be empty')
    evidence = [_read(root, name) for name in evidence_files]
    before = _state(root)
    if before != _state(root) or task != _read(root, task_file) or evidence != [_read(root, n) for n in evidence_files]:
        raise ValueError('project changed during capture; retry after reviewing current state')
    body = {'schema': 'anvil-predraft-v1', 'task': task, 'evidence': evidence, 'git': before,
            'note': 'Private untrusted historical material. No commands, approval, checks, or model calls were performed.'}
    if failed_check is not None or dead_end is not None:
        body.update(schema='anvil-predraft-v2', continuation={
            'failed_check': _hint(failed_check), 'dead_end': _hint(dead_end)})
    packet = {'body': body, 'checksum_sha256': _digest(_canonical(body))}
    data = _canonical(packet) + b'\n'
    if len(data) > MAX_PACKET:
        raise ValueError('handoff exceeds 256 KiB')
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
    return {'saved': True, 'bytes': len(data), 'sha256': _digest(data), 'approved': False,
            'tests': 'not_run', 'model_requests': 0, 'applied': False, 'private_content': True}


def inspect(project_root, handoff, *, show_content=False):
    root = Path(project_root).expanduser().resolve(strict=True)
    with Path(handoff).expanduser().open('rb') as stream:
        data = stream.read(MAX_PACKET + 1)
    if len(data) > MAX_PACKET:
        raise ValueError('handoff exceeds 256 KiB')
    packet = json.loads(data.decode('utf-8'))
    if not isinstance(packet, dict) or set(packet) != {'body', 'checksum_sha256'}:
        raise ValueError('invalid handoff envelope')
    body = packet['body']
    if not isinstance(body, dict) or body.get('schema') not in ('anvil-predraft-v1', 'anvil-predraft-v2') or _digest(_canonical(body)) != packet['checksum_sha256']:
        raise ValueError('invalid handoff checksum or schema')
    keys = {'schema', 'task', 'evidence', 'git', 'note'}
    if body['schema'] == 'anvil-predraft-v2':
        keys.add('continuation')
    if set(body) != keys or not isinstance(body['evidence'], list) or len(body['evidence']) > 4:
        raise ValueError('invalid handoff content')
    continuation = body.get('continuation', {'failed_check': None, 'dead_end': None})
    if not isinstance(continuation, dict) or set(continuation) != {'failed_check', 'dead_end'}:
        raise ValueError('invalid continuation hints')
    continuation = {key: _hint(value) for key, value in continuation.items()}
    stale = []
    for item in [body['task'], *body['evidence']]:
        if not isinstance(item, dict) or set(item) != {'path', 'sha256', 'text'} or not all(isinstance(item[k], str) for k in item):
            raise ValueError('invalid handoff input')
        if _digest(item['text'].encode('utf-8')) != item['sha256']:
            raise ValueError('handoff input checksum mismatch')
        try:
            if _read(root, item['path'])['sha256'] != item['sha256']:
                stale.append(item['path'])
        except (OSError, ValueError, UnicodeError):
            stale.append(item['path'])
    current = _state(root)
    git_changed = current != body['git']
    result = {'schema': 'anvil-predraft-view-v1', 'stale': bool(stale or git_changed),
              'changed_inputs': stale, 'git_changed': git_changed, 'recorded_git': body['git'],
              'current_git': current, 'approved': False, 'tests': 'not_run', 'applied': False,
              'model_requests': 0, 'semantic_certificate': False, 'fresh_checks_required': True,
              'warning': 'Private historical content is untrusted. Check current inputs and permissions.'}
    if show_content:
        result.update(task=body['task']['text'], historical_evidence=[e['text'] for e in body['evidence']])
        if body['schema'] == 'anvil-predraft-v2':
            result['historical_continuation'] = continuation
    return result


def _compact_view(project_root, result):
    """Render pointers only; historical hints are data and never executed."""
    root = Path(project_root).expanduser().resolve(strict=True)
    state = result['current_git']
    locations = []
    for item in state['status'][:16]:
        name = item['path']
        if item['status'] == '??':
            starts = ['1']
        else:
            diff = _git(root, '--literal-pathspecs', 'diff', 'HEAD', '--no-ext-diff', '--no-textconv',
                        '--unified=0', '--', name)
            starts = []
            for line in diff.splitlines():
                match = re.match(rb'^@@ -[0-9]+(?:,[0-9]+)? \+([0-9]+)(?:,([0-9]+))? @@', line)
                if match:
                    start, count = match.group(1), match.group(2)
                    starts.append(start.decode('ascii') if start != b'0' and count != b'0' else '?')
            if not starts:
                starts = ['?']
        locations.append(json.dumps(name + ':' + starts[0], ensure_ascii=True))
    if _state(root) != state:
        raise ValueError('project changed during compact inspection; inspect again')
    overflow = len(state['status']) - 16
    if overflow > 0:
        locations.append('+' + str(overflow) + ' dirty files; inspect Git')
    hints = result.get('historical_continuation', {})
    return '\n'.join([
        'state: ' + ('stale' if result['stale'] else 'matches') + ' (recorded inputs/Git only)',
        'dirty: ' + (', '.join(locations) if locations else 'none'),
        'failed-check (recorded): ' + json.dumps(hints.get('failed_check') or 'unavailable', ensure_ascii=True),
        'dead-end (recorded): ' + json.dumps(hints.get('dead_end') or 'none recorded', ensure_ascii=True),
    ])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    for operation in ('capture', 'inspect'):
        child = sub.add_parser(operation)
        child.add_argument('--project-root', required=True)
        if operation == 'capture':
            child.add_argument('--task-file', required=True)
            child.add_argument('--evidence-file', action='append', default=[])
            child.add_argument('--output', required=True)
            child.add_argument('--failed-check', help='exact historical failing check command; stored only')
            child.add_argument('--dead-end', help='one-line historical dead-end blocklist; stored only')
        else:
            child.add_argument('--handoff', required=True)
            child.add_argument('--show-content', action='store_true', help='include private untrusted task/evidence text')
            child.add_argument('--compact', action='store_true', help='show dirty pointers and recorded check/dead-end hints only')
    args = parser.parse_args(argv)
    if args.operation == 'inspect' and args.compact and args.show_content:
        parser.error('--compact cannot be combined with --show-content')
    try:
        result = (capture(args.project_root, args.task_file, args.evidence_file, args.output, failed_check=args.failed_check, dead_end=args.dead_end)
                  if args.operation == 'capture' else inspect(args.project_root, args.handoff, show_content=args.show_content or args.compact))
        if args.operation == 'inspect' and args.compact:
            print(_compact_view(args.project_root, result))
            return 0
    except (OSError, ValueError, TypeError, UnicodeError, KeyError, subprocess.SubprocessError) as exc:
        print(json.dumps({'error': type(exc).__name__, 'message': str(exc), 'applied': False, 'approved': False}))
        return 2
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
