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
import shutil
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_FILES = {
    'anvil_alpha/__init__.py', 'anvil_alpha/cli.py', 'anvil_alpha/codec.py',
    'anvil_workbench/__init__.py', 'anvil_workbench/__main__.py',
    'anvil_workbench/workbench.py', 'anvil_workbench/proposal_checks.py',
    'anvil_workbench/capture_candidate.py', 'anvil_workbench/jobs.py',
    'anvil_workbench/pre_draft.py',
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


def run(command, cwd, env, *, text='', expected_exit=0):
    result = subprocess.run(command, cwd=cwd, env=env, input=text,
                            text=True, capture_output=True, timeout=120)
    if result.returncode != expected_exit:
        raise RuntimeError(f'expected exit {expected_exit}, got {result.returncode}: '
                           + (result.stdout + result.stderr)[-3000:])
    return result.stdout


def rows(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def verify_handoff(root, binaries, python, env):
    project = root / 'handoff-project'
    project.mkdir()
    git = shutil.which('git')
    if git is None:
        raise RuntimeError('Git is required for the installed handoff fixture')
    env = dict(env, PATH=str(Path(git).parent) + os.pathsep + env['PATH'])

    def command(name, *args, expected_exit=0):
        executable = binaries / (name + '.exe' if os.name == 'nt' else name)
        return run([str(executable), *args], project, env, expected_exit=expected_exit)

    def git_command(*args):
        return run([git, *args], project, env)

    original = b'def helper():\n    return 1\n\ndef value():\n    return helper()\n\ndef other():\n    return 7\n'
    source = project / 'sample.py'
    source.write_bytes(original)
    (project / 'task.txt').write_text('Return helper plus one.', encoding='utf-8')
    (project / 'check.py').write_text('from sample import value, other\n'
                                     'assert value() == 2 and other() == 9\n', encoding='utf-8')
    git_command('init', '-q')
    git_command('config', 'core.autocrlf', 'false')
    git_command('add', 'sample.py', 'task.txt', 'check.py')
    git_command('-c', 'commit.gpgsign=false', '-c', 'user.name=Synthetic', '-c',
                'user.email=test@example.invalid', 'commit', '-qm', 'Fixture')

    (project / 'candidate.py').write_bytes(original.replace(b'return helper()', b'return helper() + 1'))
    capture_args = ['--project-root', str(project), '--source', 'sample.py', '--candidate', 'candidate.py',
                    '--symbol', 'value', '--context-symbol', 'helper', '--intent-file', 'task.txt',
                    '--source-sha256', hashlib.sha256(original).hexdigest()]
    assert json.loads(command('anvil-capture', *capture_args, '--output', 'pending.json'))['tests'] == 'not_run'
    command('anvil-capture', *capture_args, '--output', 'failed.json', '--check-failed')
    job_args = ['--project-root', str(project), '--intent-file', 'task.txt', '--json']
    failed = json.loads(command('anvil-job', *job_args, '--export-patch', 'blocked.patch', 'failed.json',
                                expected_exit=2))
    assert failed['items'][0]['status'] == 'quarantined' and not (project / 'blocked.patch').exists()

    changed = original.replace(b'return 7', b'return 9')
    source.write_bytes(changed)
    handoff = str(root / 'private-handoff.json')
    command('anvil-predraft', 'capture', '--project-root', str(project), '--task-file', 'task.txt',
            '--output', handoff, '--failed-check', 'python check.py', '--dead-end', 'Skip the previous draft')
    compact = command('anvil-predraft', 'inspect', '--project-root', str(project), '--handoff', handoff,
                      '--compact').splitlines()
    assert len(compact) == 4 and 'sample.py:8' in compact[1] and 'python check.py' in compact[2]
    assert 'Skip the previous draft' in compact[3] and 'Return helper plus one.' not in '\n'.join(compact)

    source.write_bytes(changed.replace(b'return 1', b'return 3'))
    dependency = json.loads(command('anvil-job', *job_args, '--export-patch', 'drift.patch', 'pending.json',
                                    expected_exit=2))
    assert dependency['items'][0]['status'] == 'reassess_dependencies'
    assert not (project / 'drift.patch').exists()
    source.write_bytes(changed)
    result = json.loads(command('anvil-job', *job_args, '--export-patch', 'resume.patch', 'pending.json'))
    assert result['exported'] and result['tests'] == 'not_run' and result['model_requests'] == 0
    assert not result['approved'] and not result['applied'] and source.read_bytes() == changed
    git_command('apply', '--check', 'resume.patch')
    git_command('apply', 'resume.patch')  # Operator step in the disposable fixture.
    run([str(python), 'check.py'], project, env)


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
        verify_handoff(root, binaries, python, env)
    print(json.dumps({'status': 'PASS', 'runtime_files': len(RUNTIME_FILES),
                      'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
                      'clean_install': True, 'checkout_imports': False,
                      'offline_restore_export': True, 'stale_restore_refused': True,
                      'oversized_input_recovery_prompts': 3,
                      'compact_handoff_and_fresh_git_check': True,
                      'refused_failed_draft_and_changed_helper': True,
                      'restored_approval': False, 'model_requests': 0,
                      'scope': 'fixed-fixture packaging smoke, not useful-job economics'}, indent=2))


if __name__ == '__main__':
    main()
