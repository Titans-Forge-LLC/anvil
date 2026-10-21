"""Verify a built wheel in a fresh, offline environment outside the checkout.

This is a packaging smoke test with a fixed answer, not a model-quality or
performance experiment. No backend or external network is needed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_FILES = {
    'anvil_alpha/__init__.py', 'anvil_alpha/cli.py', 'anvil_alpha/codec.py',
    'anvil_workbench/__init__.py', 'anvil_workbench/__main__.py',
    'anvil_workbench/workbench.py', 'anvil_workbench/proposal_checks.py',
}


def verify_wheel(wheel):
    """Bind installed runtime bytes to this reviewed source; reject extras."""
    with zipfile.ZipFile(wheel) as archive:
        members = archive.namelist()
        if len(members) != len(set(members)):
            raise ValueError('duplicate wheel members')
        runtime = {name for name in members if '.dist-info/' not in name}
        if runtime != RUNTIME_FILES:
            raise ValueError('unexpected wheel runtime boundary')
        for name in runtime:
            if archive.read(name) != (ROOT / 'src' / name).read_bytes():
                raise ValueError('wheel source mismatch: ' + name)
        metadata = [name for name in members if name.endswith('.dist-info/METADATA')]
        if len(metadata) != 1:
            raise ValueError('ambiguous wheel distribution')
        prefix = metadata[0][:-len('METADATA')]
        if any(name not in runtime and not name.startswith(prefix) for name in members):
            raise ValueError('unexpected wheel metadata boundary')
        if any(line.startswith('Requires-Dist:') for line in archive.read(metadata[0]).decode().splitlines()):
            raise ValueError('model-free runtime acquired a mandatory dependency')


def clean_environment(root):
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    env.update(PATH=os.defpath, HOME=str(root), USERPROFILE=str(root),
               TMPDIR=str(root), TEMP=str(root), TMP=str(root),
               PIP_NO_INDEX='1', PIP_DISABLE_PIP_VERSION_CHECK='1',
               PIP_CONFIG_FILE=os.devnull, PYTHONDONTWRITEBYTECODE='1')
    return env


def run(command, cwd, env, *, text=''):
    result = subprocess.run(command, cwd=cwd, env=env, input=text,
                            text=True, capture_output=True, timeout=120)
    if result.returncode:
        raise RuntimeError('installed command failed: ' + result.stderr[-3000:])
    return result.stdout


def rows(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel-dir', type=Path, required=True)
    args = parser.parse_args()
    wheels = list(args.wheel_dir.resolve(strict=True).glob('anvil_reference-*.whl'))
    if len(wheels) != 1:
        parser.error('wheel directory must contain exactly one anvil-reference wheel')
    wheel = wheels[0]
    verify_wheel(wheel)
    with tempfile.TemporaryDirectory(prefix='anvil-installed-') as temporary:
        root = Path(temporary).resolve()
        project, environment = root / 'project', root / 'environment'
        project.mkdir()
        env = clean_environment(root)
        run([sys.executable, '-I', '-m', 'venv', str(environment)], project, env)
        binaries = environment / ('Scripts' if os.name == 'nt' else 'bin')
        python = binaries / ('python.exe' if os.name == 'nt' else 'python')
        executable = binaries / ('anvil-workbench.exe' if os.name == 'nt' else 'anvil-workbench')
        codec = binaries / ('anvil.exe' if os.name == 'nt' else 'anvil')
        run([str(python), '-I', '-m', 'pip', 'install', '--no-index', '--no-deps',
             '--no-compile', str(wheel)], project, env)
        help_text = run([str(executable), '--help'], project, env)
        module_help = run([str(python), '-I', '-m', 'anvil_workbench', '--help'], project, env)
        if '--backend' not in help_text or '--backend' not in module_help:
            raise AssertionError('installed workbench entry points unavailable')
        run([str(codec), '--help'], project, env)
        # Only the installed package creates this fixed, explicitly synthetic draft.
        driver = '''import hashlib,json,pathlib,sys
from anvil_workbench import workbench as w
from anvil_workbench.proposal_checks import TestRunner
assert pathlib.Path(w.__file__).resolve().is_relative_to(pathlib.Path(sys.prefix).resolve())
assert not any(name == 'mlx' or name.startswith('mlx.') for name in sys.modules)
root = pathlib.Path.cwd()
source = root / 'sample.py'
source.write_bytes(b'def value():\\n    return 1\\n')
class FixedFixture:
    def complete(self, *args, **kwargs):
        return {'complete': True, 'text': 'def value():\\n    return 2\\n'}
session = w.ProposalSession(FixedFixture())
result = session.propose({'file': str(source), 'symbol': 'value', 'instruction': 'Return 2.'})
assert result['reviewable'] is True
session.save_checkpoint(result['proposal_id'], root, root / 'saved.anvil-checkpoint.json')
session.export_patch(result['proposal_id'], root, root / 'expected.patch')
restarted = w.ProposalSession(w.OfflineCompletion())
loaded = restarted.load_checkpoint(root / 'saved.anvil-checkpoint.json', root)
assert restarted.check_status(loaded['proposal_id']) == {'tests': 'not_run', 'approved': False}
assert 'executed_check' not in restarted.proposals[loaded['proposal_id']]
(root / 'check.py').write_text('from sample import value\\nassert value() == 2\\n')
plan = {'schema':'anvil-python-check-plan-v1','files':['sample.py','check.py'],
        'test_file':'check.py','timeout_seconds':5}
(root / 'checks.json').write_text(json.dumps(plan))
TestRunner(root, root / 'checks.json').fresh_inputs()
print(json.dumps({'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}))
'''
        baseline = json.loads(run([str(python), '-I', '-c', driver], project, env))
        requests = [
            {'load': str(project / 'saved.anvil-checkpoint.json'), 'project_root': str(project)},
            {'export': 'p1', 'project_root': str(project), 'output': str(project / 'resumed.patch')},
        ]
        restored = rows(run([str(executable), '--backend', 'offline'], project, env,
                            text=''.join(json.dumps(x) + '\n' for x in requests)))
        if (len(restored) != 3 or restored[0].get('backend') != 'offline'
                or restored[1].get('restored') is not True
                or restored[1].get('model_requests') != 0
                or restored[1].get('approved', False) is not False
                or 'executed_check' in restored[1]
                or any('error' in row for row in restored)):
            raise AssertionError('offline restore did not preserve evidence boundaries')
        if (project / 'resumed.patch').read_bytes() != (project / 'expected.patch').read_bytes():
            raise AssertionError('installed restart changed the patch')
        checkpoint = project / 'saved.anvil-checkpoint.json'
        checkpoint_before = checkpoint.read_bytes()
        oversized = 'x' * 20000 + '\n'
        for name in ('file', 'action', 'destination'):
            destination = 'interactive-' + name + '.patch'
            load = ':load saved.anvil-checkpoint.json\n'
            answers = {
                'file': oversized + load + 'e\n' + destination + '\nq\n',
                'action': load + oversized + 'e\n' + destination + '\nq\n',
                'destination': load + 'e\n' + oversized + destination + '\nq\n',
            }[name]
            transcript = run([str(executable), '--backend', 'offline', '--interactive',
                              '--project-root', str(project)], project, env, text=answers)
            if (project / destination).read_bytes() != (project / 'expected.patch').read_bytes():
                raise AssertionError('installed oversized input lost the pending export')
            if checkpoint.read_bytes() != checkpoint_before:
                raise AssertionError('installed recovery modified the checkpoint')
            if 'Try a shorter answer.' not in transcript or 'x' * 100 in transcript:
                raise AssertionError('installed recovery failed to reject input safely')
        source = project / 'sample.py'
        if hashlib.sha256(source.read_bytes()).hexdigest() != baseline['source_sha256']:
            raise AssertionError('offline restore/export modified source')
        source.write_bytes(source.read_bytes() + b'# changed after checkpoint\n')
        stale = rows(run([str(executable), '--backend', 'offline'], project, env,
                         text=json.dumps(requests[0]) + '\n'))
        if (len(stale) != 2 or stale[1].get('error') != 'ValueError'
                or stale[1].get('applied') is not False):
            raise AssertionError('stale source was not refused')
    print(json.dumps({'status': 'PASS', 'runtime_files': len(RUNTIME_FILES),
                      'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
                      'clean_install': True, 'checkout_imports': False,
                      'offline_restore_export': True, 'stale_restore_refused': True,
                      'oversized_input_recovery_prompts': 3,
                      'restored_approval': False, 'model_requests': 0,
                      'scope': 'fixed-fixture packaging smoke, not useful-job economics'}, indent=2))


if __name__ == '__main__':
    main()
