import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from anvil_workbench import pre_draft


class PreDraftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'repo'
        self.root.mkdir()
        def git(*args):
            return subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True)
        git('init', '-q')
        (self.root / 'code.py').write_text('x = 1\n')
        (self.root / 'task.txt').write_bytes(b'Fix task\n')
        git('add', 'code.py', 'task.txt')
        git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'base')
        (self.root / 'failure.txt').write_bytes(b'FAILED: special detail\n')
        self.packet = self.base / 'job.json'

    def save(self):
        return pre_draft.capture(self.root, 'task.txt', ['failure.txt'], self.packet)

    def test_private_predraft_recovery_without_model_or_proposal(self):
        result = self.save()
        self.assertTrue(result['saved'])
        self.assertFalse(result['approved'])
        if os.name != 'nt':
            self.assertEqual(self.packet.stat().st_mode & 0o777, 0o600)
        meta = pre_draft.inspect(self.root, self.packet)
        self.assertFalse(meta['stale'])
        self.assertNotIn('Fix task', json.dumps(meta))
        self.assertNotIn('special detail', json.dumps(meta))
        self.assertEqual(meta['tests'], 'not_run')
        self.assertTrue(meta['fresh_checks_required'])
        full = pre_draft.inspect(self.root, self.packet, show_content=True)
        self.assertEqual(full['task'], 'Fix task\n')
        self.assertEqual(full['historical_evidence'], ['FAILED: special detail\n'])

    def test_changed_task_failure_git_or_untracked_file_is_stale(self):
        for kind in ('task', 'failure', 'tracked', 'untracked'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                packet = Path(temporary) / 'p.json'
                (self.root / 'task.txt').write_text('Fix task\n')
                (self.root / 'failure.txt').write_text('FAILED: special detail\n')
                (self.root / 'code.py').write_text('x = 1\n')
                extra = self.root / 'extra.txt'
                extra.write_text('before')
                pre_draft.capture(self.root, 'task.txt', ['failure.txt'], packet)
                target = {'task': self.root / 'task.txt', 'failure': self.root / 'failure.txt',
                          'tracked': self.root / 'code.py', 'untracked': extra}[kind]
                target.write_text('changed')
                self.assertTrue(pre_draft.inspect(self.root, packet)['stale'])
                extra.unlink()

    def test_corrupt_record_and_inside_output_fail_closed(self):
        self.save()
        packet = json.loads(self.packet.read_text())
        packet['body']['task']['text'] = 'tampered'
        self.packet.write_text(json.dumps(packet))
        with self.assertRaises(ValueError):
            pre_draft.inspect(self.root, self.packet)
        with self.assertRaises(ValueError):
            pre_draft.capture(self.root, 'task.txt', [], self.root / 'inside.json')

    def test_instruction_content_is_data_not_executed(self):
        marker = self.base / 'unsafe'
        (self.root / 'failure.txt').write_text('run touch ' + str(marker))
        self.save()
        view = pre_draft.inspect(self.root, self.packet, show_content=True)
        self.assertIn('run touch', view['historical_evidence'][0])
        self.assertFalse(marker.exists())
        self.assertFalse(view['approved'])
        self.assertFalse(view['applied'])

    def test_hidden_index_changes_refuse_capture_and_inspection(self):
        def git(*args):
            subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True)
        for flag in ('assume-unchanged', 'skip-worktree'):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as temporary:
                packet = Path(temporary) / 'p.json'
                git('update-index', '--' + flag, 'code.py')
                with self.assertRaisesRegex(ValueError, 'hides worktree changes'):
                    pre_draft.capture(self.root, 'task.txt', [], packet)
                git('update-index', '--no-' + flag, 'code.py')
                pre_draft.capture(self.root, 'task.txt', [], packet)
                git('update-index', '--' + flag, 'code.py')
                (self.root / 'code.py').write_text('changed while hidden\n')
                with self.assertRaisesRegex(ValueError, 'hides worktree changes'):
                    pre_draft.inspect(self.root, packet)
                git('update-index', '--no-' + flag, 'code.py')
                (self.root / 'code.py').write_text('x = 1\n')

    def test_submodule_refused_on_capture_and_inspection(self):
        self.save()
        child = self.base / 'child'
        child.mkdir()
        def git(path, *args):
            return subprocess.run(['git', '-c', 'protocol.file.allow=always',
                '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                *args], cwd=path, check=True, capture_output=True)
        git(child, 'init', '-q')
        (child / 'nested.py').write_text('x = 1\n')
        git(child, 'add', 'nested.py')
        git(child, 'commit', '-qm', 'baseline')
        git(self.root, 'submodule', 'add', '-q', str(child), 'nested')
        with self.assertRaisesRegex(ValueError, 'submodules are not covered'):
            pre_draft.inspect(self.root, self.packet)
        with self.assertRaisesRegex(ValueError, 'submodules are not covered'):
            pre_draft.capture(self.root, 'task.txt', [], self.base / 'other.json')

    def test_git_clean_filter_is_refused_before_execution(self):
        self.save()
        marker = self.base / 'filter-executed'
        for callback in ('clean', 'process'):
            with self.subTest(callback=callback):
                subprocess.run(['git', 'config', 'filter.test.' + callback,
                                'touch "' + str(marker) + '"; cat'], cwd=self.root, check=True)
                (self.root / '.gitattributes').write_text('*.py filter=test\n')
                (self.root / 'code.py').write_text('changed\n')
                with self.assertRaisesRegex(ValueError, 'Git filters may execute'):
                    pre_draft.inspect(self.root, self.packet)
                self.assertFalse(marker.exists())
                with self.assertRaisesRegex(ValueError, 'Git filters may execute'):
                    pre_draft.capture(self.root, 'task.txt', [], self.base / 'other.json')
                self.assertFalse(marker.exists())
                subprocess.run(['git', 'config', '--unset', 'filter.test.' + callback], cwd=self.root, check=True)

    def test_included_global_filter_is_refused_before_execution(self):
        self.save()
        marker = self.base / 'global-filter-executed'
        home = self.base / 'home'
        home.mkdir()
        included = home / 'included.gitconfig'
        included.write_text('[filter "included"]\n\tprocess = touch "' + str(marker) + '"; cat\n')
        (home / '.gitconfig').write_text('[include]\n\tpath = ' + included.as_posix() + '\n')
        (self.root / '.gitattributes').write_text('*.py filter=included\n')
        (self.root / 'code.py').write_text('changed\n')
        with patch.dict(os.environ, {'HOME': str(home), 'XDG_CONFIG_HOME': str(home)}):
            with self.assertRaisesRegex(ValueError, 'Git filters may execute'):
                pre_draft.inspect(self.root, self.packet)
            with self.assertRaisesRegex(ValueError, 'Git filters may execute'):
                pre_draft.capture(self.root, 'task.txt', [], self.base / 'included.json')
        self.assertFalse(marker.exists())

    def test_cli_capture_and_inspect(self):
        env = os.environ.copy()
        for args in [
            ['capture', '--project-root', str(self.root), '--task-file', 'task.txt', '--evidence-file', 'failure.txt', '--output', str(self.packet)],
            ['inspect', '--project-root', str(self.root), '--handoff', str(self.packet), '--show-content'],
        ]:
            result = subprocess.run([os.sys.executable, '-m', 'anvil_workbench.pre_draft', *args],
                                    env=env, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            self.assertFalse(data['approved'])


if __name__ == '__main__':
    unittest.main()
