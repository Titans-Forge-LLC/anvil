"""Offline multi-file handoff summary and pending-patch export over Git."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path

from .workbench import OfflineCompletion, ProposalSession, _job_packet


def _read(path, limit):
    with path.open('rb') as stream:
        value = stream.read(limit + 1)
    if len(value) > limit:
        raise ValueError('job input exceeds its byte limit')
    return value


def _inside(root, value):
    path = Path(value).expanduser()
    path = (root / path).resolve(strict=True)
    path.relative_to(root)
    if not path.is_file():
        raise ValueError('job input must be a regular file')
    return path


def _patch(relative, original, replacement):
    if any(c in relative for c in '\\"\t\r\n'):
        raise ValueError('source path contains unsupported patch header characters')

    def lines(data):
        parts = data.split(b'\n')
        return [part + b'\n' for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])

    diff = difflib.diff_bytes(difflib.unified_diff, lines(original), lines(replacement),
        fromfile=('a/' + relative + '\t').encode('utf-8'),
        tofile=('b/' + relative + '\t').encode('utf-8'))
    return b''.join(line if line.endswith(b'\n') else
                    line + b'\n\\ No newline at end of file\n' for line in diff)


def inspect_jobs(project_root, intent_file, capsules, *, export_patch=None):
    """Inspect distinct files; optionally export pending changes, never apply."""
    if not isinstance(capsules, (list, tuple)) or not 1 <= len(capsules) <= 16:
        raise ValueError('supply 1..16 job capsules, one per source file')
    root = Path(project_root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError('project_root must be a directory')
    intent_path = _inside(root, intent_file)
    intent_raw = _read(intent_path, 16384)
    instruction = intent_raw.decode('utf-8')
    if not instruction.strip() or len(instruction) > 4000 or '\x00' in instruction:
        raise ValueError('current intent must contain 1..4000 UTF-8 characters')
    bound = {intent_path: (intent_raw, 16384)}
    session = ProposalSession(OfflineCompletion())
    items, pending, seen_capsules, seen_sources = [], [], set(), set()
    states = {'retained_change_present': 'already_present', 'resumable': 'pending',
              'needs_reconciliation': 'conflicting', 'dependencies_changed': 'reassess_dependencies',
              'quarantined': 'quarantined'}
    for value in capsules:
        capsule = _inside(root, value)
        if capsule in seen_capsules:
            raise ValueError('duplicate job capsule')
        seen_capsules.add(capsule)
        packet, source, raw = _job_packet(capsule, root)
        if source in seen_sources:
            raise ValueError('this version accepts one capsule per source file')
        seen_sources.add(source)
        view = session.inspect_job(capsule, root, instruction)
        current = _read(source, 1048576)
        if (hashlib.sha256(raw).hexdigest() != view['capsule_sha256']
                or hashlib.sha256(current).hexdigest() != view['source_sha256']):
            raise ValueError('source or capsule changed during job inspection')
        bound[capsule], bound[source] = (raw, 8388608), (current, 1048576)
        state = states[view['handoff_status']]
        relative = source.relative_to(root).as_posix()
        items.append({'file': relative, 'symbol': packet['symbol'], 'status': state,
                      'capsule': capsule.relative_to(root).as_posix(),
                      'source_sha256': view['source_sha256'],
                      'capsule_sha256': view['capsule_sha256'],
                      'blocking_reasons': view['blocking_reasons']})
        if state == 'pending':
            pending.append((capsule, relative, current, view['capsule_sha256']))

    def unchanged():
        for path, (raw, limit) in bound.items():
            if _read(path, limit) != raw:
                raise ValueError('job input changed; inspect again before export')

    blocked = any(row['status'] in ('conflicting', 'reassess_dependencies', 'quarantined') for row in items)
    unchanged()
    result = {'schema': 'anvil-job-summary-v1', 'items': items, 'blocked': blocked,
              'pending_files': len(pending),
              'already_present_files': sum(row['status'] == 'already_present' for row in items),
              'quarantined_files': sum(row['status'] == 'quarantined' for row in items),
              'intent_sha256': hashlib.sha256(intent_raw).hexdigest(),
              'model_requests': 0, 'tests': 'not_run', 'approved': False, 'applied': False,
              'semantic_certificate': False, 'fresh_checks_required': True,
              'dependency_coverage': 'explicit capsule helpers and module environment only',
              'exported': False, 'output': None}
    if blocked:
        result['next_step'] = 'Repair or quarantine failures and reassess conflicts/dependencies; no combined patch can be exported.'
        return result
    if not pending:
        result['next_step'] = 'Retained functions are present. Run current checks and review before completing the job.'
        return result
    if export_patch is None:
        result['next_step'] = 'Use --export-patch PATH to export only pending edits, then review and run current checks.'
        return result
    destination = Path(export_patch).expanduser()
    destination = (root / destination).absolute()
    parent = destination.parent.resolve(strict=True)
    parent.relative_to(root)
    destination = parent / destination.name
    if destination.is_symlink() or destination.exists():
        raise FileExistsError('patch destination already exists')
    patches = []
    for capsule, relative, original, capsule_hash in pending:
        restored = session.resume_job(capsule, root, instruction)
        if (hashlib.sha256(original).hexdigest() != restored['source_sha256']
                or capsule_hash != restored['capsule_sha256']
                or restored['quarantined']):
            raise ValueError('source or capsule changed while preparing pending edits')
        replacement = restored['replacement_text'].encode('utf-8')
        patches.append(_patch(relative, original, replacement))
    data = b''.join(patches)
    if not data:
        raise ValueError('no pending changes to export')
    # A point-in-time check, not a lock against concurrent editors or link swaps.
    unchanged()
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
    result.update(exported=True, output=destination.relative_to(root).as_posix(),
                  patch_bytes=len(data), patch_sha256=hashlib.sha256(data).hexdigest(),
                  next_step='Review the patch, use git apply --check before application, then run current checks.')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', required=True, help='existing project directory')
    parser.add_argument('--intent-file', required=True, help='file containing your exact current saved task text')
    parser.add_argument('--export-patch', help='create a new Git patch inside the project; no source application')
    parser.add_argument('--json', action='store_true', help='metadata-only summary for another agent')
    parser.add_argument('capsules', nargs='+', help='1..16 private capsules, one per source file')
    args = parser.parse_args(argv)
    try:
        result = inspect_jobs(args.project_root, args.intent_file, args.capsules, export_patch=args.export_patch)
    except (OSError, RuntimeError, UnicodeError, ValueError, SyntaxError, RecursionError) as exc:
        if args.json:
            print(json.dumps({'error': type(exc).__name__, 'message': str(exc),
                              'applied': False, 'model_requests': 0}, ensure_ascii=True))
        else:
            print('Job inspection refused: ' + json.dumps(str(exc), ensure_ascii=True))
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=True))
    else:
        for row in result['items']:
            print(row['status'] + ': ' + json.dumps(row['file'], ensure_ascii=True) + ' :: ' + row['symbol'])
        print(result['next_step'])
        if result['exported']:
            print('Exported ' + json.dumps(result['output'], ensure_ascii=True))
        print('Model requests: 0 | current tests: not run | source applied: no')
    return 2 if result['blocked'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
