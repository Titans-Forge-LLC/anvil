"""Real sandbox checks on macOS; deterministic plan tests on every platform."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('proposal_checks', Path(__file__).resolve().parents[1] / 'experiments/proposal_checks.py')
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)


class PlanTests(unittest.TestCase):
    def fixture(self, root, test='from sample import value\nassert value() == 2\n', timeout=5):
        source = root / 'sample.py'
        source.write_text('def value():\n    return 1\n')
        (root / 'check.py').write_text(test)
        plan = root / 'plan.json'
        plan.write_text(json.dumps(dict(schema='anvil-python-check-plan-v1',
            files=['sample.py', 'check.py'], test_file='check.py', timeout_seconds=timeout)))
        proposal = dict(file=str(source), source_sha256=C.digest(source.read_bytes()),
                        text='def value():\n    return 2\n')
        return C.TestRunner(root, plan), proposal

    def test_plan_and_all_inputs_frozen(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner, _ = self.fixture(root)
            runner.fresh_inputs()
            (root / 'check.py').write_text('raise SystemExit(0)')
            with self.assertRaisesRegex(ValueError, 'inputs changed'): runner.fresh_inputs()
            runner, _ = self.fixture(root)
            runner.plan_path.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'plan changed'): runner.fresh_inputs()

    def test_invalid_paths_and_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner, _ = self.fixture(root)
            original = json.loads(runner.plan_raw)
            for changes in ({'timeout_seconds':True}, {'timeout_seconds':121}, {'files':['../secret']},
                            {'files':['sample.py','sample.py']}, {'command':['sh']}, {'test_file':[]},
                            {'files':['/tmp/secret','check.py']}):
                with self.subTest(changes=changes):
                    runner.plan_path.write_text(json.dumps(dict(original, **changes)))
                    with self.assertRaises(ValueError): C.TestRunner(root, runner.plan_path)

    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner, _ = self.fixture(root)
            try:
                (root / 'link.py').symlink_to(root / 'sample.py')
            except OSError:
                self.skipTest('symlink creation unavailable on this host')
            with self.assertRaisesRegex(ValueError, 'symlink'): C.relative_file(root, 'link.py')

    def test_unsupported_has_no_unrestricted_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            runner, proposal = self.fixture(Path(directory))
            with patch.object(runner, 'available', return_value=False), patch.object(C.subprocess, 'Popen') as run:
                with self.assertRaisesRegex(ValueError, 'no unrestricted fallback'): runner.run(proposal)
                run.assert_not_called()


@unittest.skipUnless(C.TestRunner.available(), 'live checks require macOS sandbox-exec')
class ExecutionTests(unittest.TestCase):
    fixture = PlanTests.fixture

    def test_candidate_pass_and_failure_do_not_modify_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner, proposal = self.fixture(root)
            before = (root / 'sample.py').read_bytes()
            passed = runner.run(proposal)
            self.assertEqual(passed['tests'], 'executed_zero_exit', passed['output_tail'])
            self.assertFalse(passed['approved'])
            self.assertFalse(passed['applied'])
            self.assertEqual(passed['model_requests'], 0)
            self.assertEqual(passed['candidate_sha256'], hashlib.sha256(proposal['text'].encode()).hexdigest())
            proposal['text'] = before.decode()
            failed = runner.run(proposal)
            self.assertEqual(failed['tests'], 'executed_nonzero_exit', failed['output_tail'])
            self.assertEqual((root / 'sample.py').read_bytes(), before)

    def test_network_host_reads_writes_and_input_mutation_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            secret = root / 'not-declared.txt'
            secret.write_text('not available to child')
            test = '''import os, pathlib, socket, tempfile, subprocess
def denied(action):
    try: action()
    except (OSError, RuntimeError): return
    raise AssertionError('forbidden action succeeded')
denied(lambda: pathlib.Path(SECRET_PATH).read_text())
denied(lambda: pathlib.Path(SECRET_PATH).write_text('changed'))
denied(lambda: pathlib.Path('sample.py').write_text('changed'))
denied(lambda: socket.socket().connect(('127.0.0.1', 9)))
denied(lambda: subprocess.run(['/usr/bin/true']))
assert 'ANVIL_TEST_SECRET' not in os.environ
with tempfile.TemporaryDirectory() as tmp:
    pathlib.Path(tmp, 'allowed').write_text('scratch only')
print('boundaries enforced')
'''.replace('SECRET_PATH', repr(str(secret)))
            runner, proposal = self.fixture(root, test)
            with patch.dict(C.os.environ, {'ANVIL_TEST_SECRET':'private'}):
                result = runner.run(proposal)
            self.assertEqual(result['tests'], 'executed_zero_exit', result['output_tail'])
            self.assertIn('boundaries enforced', result['output_tail'])
            self.assertEqual(secret.read_text(), 'not available to child')

    def test_timeout_and_output_limit_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            runner, proposal = self.fixture(Path(directory), 'import time\ntime.sleep(10)\n', timeout=1)
            result = runner.run(proposal)
            self.assertEqual(result['tests'], 'timed_out')
            self.assertLess(result['elapsed_seconds'], 5)
            runner, proposal = self.fixture(Path(directory), 'import os\nwhile True: os.write(1,b"x"*65536)\n')
            result = runner.run(proposal)
            self.assertEqual(result['tests'], 'executed_nonzero_exit')
            self.assertTrue(result['output_truncated'])
            self.assertLessEqual(len(result['output_tail']), 8192)

    def test_stale_and_test_entry_candidate_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner, proposal = self.fixture(root)
            proposal['source_sha256'] = '0'*64
            with patch.object(C.subprocess, 'Popen') as run:
                with self.assertRaisesRegex(ValueError, 'source changed'): runner.run(proposal)
                proposal['file'] = str(root/'check.py')
                with self.assertRaisesRegex(ValueError, 'test entry'): runner.run(proposal)
                run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
