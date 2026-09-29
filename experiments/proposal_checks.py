"""Opt-in, local Python checks against a disposable candidate snapshot.

macOS sandbox-exec only; never fall back to unrestricted execution. A zero
exit is evidence about this process, not a proof of correctness or approval.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import signal
import subprocess
import sys
import tempfile
import time
import unicodedata


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')


def read_bounded(path, limit=1048576):
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('check input exceeds size limit')
    return raw


def relative_file(root, name):
    if (not isinstance(name, str) or not name or '\\' in name or ':' in name
            or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        raise ValueError('check paths must be portable project-relative files')
    parts = PurePosixPath(name).parts
    if name != '/'.join(parts) or name.startswith('/') or any(p in ('.', '..') for p in parts):
        raise ValueError('check path is not canonical or escapes project')
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('symlink check inputs are not supported')
    path.resolve(strict=True).relative_to(root)
    if not path.is_file():
        raise ValueError('check input is not a regular file')
    return path


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate test plan key')
        result[key] = value
    return result


class TestRunner:
    """Operator-selected plan, frozen inputs; model output cannot choose checks."""

    def __init__(self, project_root, plan_path):
        self.root = Path(project_root).expanduser().resolve(strict=True)
        self.plan_path = Path(plan_path).expanduser().resolve(strict=True)
        self.plan_raw = read_bounded(self.plan_path, 16384)
        try:
            plan = json.loads(self.plan_raw, object_pairs_hook=unique_keys)
        except (ValueError, RecursionError):
            raise ValueError('invalid test plan JSON') from None
        if (not isinstance(plan, dict) or set(plan) != {'schema', 'files', 'test_file', 'timeout_seconds'}
                or plan['schema'] != 'anvil-python-check-plan-v1'):
            raise ValueError('invalid test plan schema')
        names = plan['files']
        if (not isinstance(names, list) or not 1 <= len(names) <= 64
                or any(not isinstance(n, str) for n in names) or len(set(names)) != len(names)):
            raise ValueError('test plan requires 1..64 distinct input files')
        if (not isinstance(plan['test_file'], str) or plan['test_file'] not in names
                or not plan['test_file'].endswith('.py')):
            raise ValueError('test_file must name a declared Python input')
        if type(plan['timeout_seconds']) is not int or not 1 <= plan['timeout_seconds'] <= 120:
            raise ValueError('check timeout must be an integer in [1, 120]')
        self.plan = plan
        raw = self._read_inputs()
        self.input_hashes = {name: digest(data) for name, data in raw.items()}

    def _read_inputs(self):
        data = {name: read_bounded(relative_file(self.root, name)) for name in self.plan['files']}
        if sum(map(len, data.values())) > 8388608:
            raise ValueError('declared check inputs exceed 8 MiB')
        return data

    def fresh_inputs(self):
        if read_bounded(self.plan_path, 16384) != self.plan_raw:
            raise ValueError('test plan changed; reload it explicitly')
        raw = self._read_inputs()
        if {name: digest(data) for name, data in raw.items()} != self.input_hashes:
            raise ValueError('check inputs changed; reload the plan explicitly')
        return raw

    @staticmethod
    def available():
        return sys.platform == 'darwin' and Path('/usr/bin/sandbox-exec').is_file()

    def run(self, proposal):
        started = time.perf_counter()
        if not self.available():
            raise ValueError('isolated checks require macOS sandbox-exec; no unrestricted fallback')
        raw = self.fresh_inputs()
        source = Path(proposal['file']).resolve(strict=True)
        name = source.relative_to(self.root).as_posix()
        if name not in raw or name == self.plan['test_file']:
            raise ValueError('candidate must be a declared input, not the test entry point')
        if digest(raw[name]) != proposal['source_sha256']:
            raise ValueError('source changed since proposal')
        candidate = proposal['text'].encode('utf-8')
        if len(candidate) > 1048576:
            raise ValueError('candidate exceeds 1 MiB')
        raw[name] = candidate
        manifest = {n: digest(b) for n, b in sorted(raw.items())}
        # A separate interpreter receives no inherited API keys, PYTHONPATH, or HOME.
        executable = Path(sys.executable).resolve(strict=True)
        runtime = Path(sys.base_prefix).resolve(strict=True)
        timeout = self.plan['timeout_seconds']
        with tempfile.TemporaryDirectory(prefix='anvil-check-') as directory:
            root = Path(directory).resolve()
            snapshot, scratch = root / 'inputs', root / 'scratch'
            snapshot.mkdir()
            scratch.mkdir()
            for item, data in raw.items():
                target = snapshot / item
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            # Only Python runtime/system files and declared inputs are readable.
            # Input writes, network, subprocess creation, and other host paths stay denied.
            read_roots = [str(snapshot), str(runtime), '/System/Library', '/usr/lib', '/usr/share']
            reads = ' '.join('(subpath ' + json.dumps(p) + ')' for p in read_roots)
            # Python's startup resolves parent directories before importing anything.
            parents = sorted({str(p) for item in (snapshot, runtime, executable) for p in item.parents})
            reads += ' ' + ' '.join('(literal ' + json.dumps(p) + ')' for p in parents)
            profile = ('(version 1)(deny default)(allow process-exec)(allow sysctl-read)(allow file-read-metadata)'
                       '(allow file-read* ' + reads + ' (literal ' + json.dumps(str(executable)) + ')'
                       ' (literal "/dev/null") (literal "/dev/urandom") (literal "/dev/random"))'
                       '(allow file-read* file-write* (subpath ' + json.dumps(str(scratch)) + '))')
            # Fixed driver, never a model-supplied command. Limits precede candidate import.
            marker = scratch / 'started'
            driver = ('import resource,runpy,sys;'
                      'resource.setrlimit(resource.RLIMIT_FSIZE,(1048576,1048576));'
                      'resource.setrlimit(resource.RLIMIT_CPU,(' + str(timeout + 1) + ',' + str(timeout + 1) + '));'
                      'sys.path.insert(0,sys.argv[1]);'
                      'open(' + repr(str(marker)) + ',"w").close();'
                      'sys.argv=[sys.argv[2]];runpy.run_path(sys.argv[0],run_name="__main__")')
            command = ['/usr/bin/sandbox-exec', '-p', profile, str(executable), '-I', '-B', '-c',
                       driver, str(snapshot), str(snapshot / self.plan['test_file'])]
            env = {'PATH': str(executable.parent), 'HOME': str(scratch), 'TMPDIR': str(scratch),
                   'LANG': 'C.UTF-8', 'ANVIL_JOB_CANDIDATE': str(snapshot / name)}
            # Parent-owned output files are outside the child's writable paths.
            timed_out = False
            with (root / 'stdout').open('w+b') as out, (root / 'stderr').open('w+b') as err:
                process = subprocess.Popen(command, cwd=snapshot, env=env, stdout=out, stderr=err,
                                           start_new_session=True)
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
                out.seek(0)
                err.seek(0)
                output = out.read(1048576) + err.read(1048576)
            # Results refer to frozen bytes. Concurrent source/test edits invalidate them.
            fresh = True
            try:
                self.fresh_inputs()
            except (OSError, ValueError):
                fresh = False
            executed = marker.exists()
            status = ('stale' if not fresh else 'timed_out' if timed_out else 'runner_error' if not executed else
                      'executed_zero_exit' if process.returncode == 0 else 'executed_nonzero_exit')
            # Strip controls before any terminal display. Full output is neither a command nor authority.
            tail = output[-8192:].decode('utf-8', errors='replace')
            tail = ''.join(c for c in tail if c in '\n\t' or unicodedata.category(c) not in ('Cc', 'Cf'))
            result = {'schema': 'anvil-executed-check-v1', 'tests': status,
                    'source_sha256': proposal['source_sha256'], 'candidate_sha256': digest(candidate),
                    'plan_sha256': digest(self.plan_raw), 'input_sha256': manifest,
                    'test_suite_sha256': digest(json_bytes({n: h for n, h in manifest.items() if n != name})),
                    'python_sha256': digest(executable.read_bytes()), 'python_version': sys.version,
                    'runner': 'macos-sandbox-exec-v1', 'profile_sha256': digest(profile.encode()),
                    'returncode': process.returncode, 'timed_out': timed_out,
                    'output_tail': tail, 'output_sha256': digest(output),
                    'output_truncated': len(output) > 8192,
                    'tests_executed': executed, 'authenticated': False, 'approved': False,
                    'model_requests': 0, 'applied': False}
        result['elapsed_seconds'] = time.perf_counter() - started
        return result
