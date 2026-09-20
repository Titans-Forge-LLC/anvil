"""Receipt behavior when optional local executables are unavailable."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('test_receipt_tool', Path(__file__).resolve().parents[1] / 'scripts/create_test_receipt.py')
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)

class ReceiptTests(unittest.TestCase):
    def test_timeout_budgets_and_private_error_handling(self):
        for function, args, budget in ((R.command_result, (['fixture'],), 300), (R.git_commit, (), 10), (R.node_version, (), 10)):
            with self.subTest(function=function.__name__):
                with patch.object(R.subprocess, 'run', side_effect=subprocess.TimeoutExpired('PRIVATE_COMMAND', budget, output='PRIVATE_OUTPUT')) as run:
                    result = function(*args)
                    self.assertEqual(run.call_args.kwargs['timeout'], budget)
                    self.assertEqual(result, {'status':'FAIL','returncode':None,'error_code':'timeout'} if function is R.command_result else None)

    def test_timeouts_still_produce_complete_failure_receipt(self):
        output = io.StringIO()
        with patch.object(R.subprocess, 'run', side_effect=subprocess.TimeoutExpired('PRIVATE_COMMAND', 300, output='PRIVATE_OUTPUT')), patch.object(sys, 'argv', ['receipt']), patch.object(sys, 'stdout', output):
            result = R.main()
        receipt = json.loads(output.getvalue())
        self.assertEqual(result, 1)
        self.assertEqual(receipt['status'], 'FAIL')
        self.assertIsNone(receipt['source']['commit'])
        self.assertIsNone(receipt['environment']['node'])
        self.assertNotIn('PRIVATE', output.getvalue())
        for key in ('python_conformance','javascript_conformance'):
            self.assertEqual(receipt['checks'][key]['error_code'], 'timeout')

    def run_receipt(self, missing):
        def run(command, **kwargs):
            if command[0] in missing:
                raise FileNotFoundError('PRIVATE_PATH_MUST_NOT_APPEAR')
            return subprocess.CompletedProcess(command, 0, stdout='fixture\n', stderr='')
        output = io.StringIO()
        with patch.object(R.subprocess, 'run', side_effect=run), patch.object(sys, 'argv', ['receipt']), patch.object(sys, 'stdout', output):
            status = R.main()
        self.assertNotIn('PRIVATE_PATH', output.getvalue())
        return status, json.loads(output.getvalue())

    def test_missing_node_is_complete_failed_receipt(self):
        status, receipt = self.run_receipt({'node'})
        self.assertEqual(status, 1)
        self.assertEqual(receipt['status'], 'FAIL')
        self.assertEqual(receipt['checks']['javascript_conformance'], {'status':'FAIL','returncode':None,'error_code':'executable_not_found'})
        self.assertIsNone(receipt['environment']['node'])
        self.assertTrue(receipt['checks']['semantic_exact'])

    def test_missing_optional_git_does_not_fail_checks(self):
        status, receipt = self.run_receipt({'git'})
        self.assertEqual(status, 0)
        self.assertEqual(receipt['status'], 'PASS')
        self.assertIsNone(receipt['source']['commit'])

    def test_missing_python_command_fails_receipt(self):
        status, receipt = self.run_receipt({sys.executable})
        self.assertEqual(status, 1)
        self.assertEqual(receipt['checks']['python_conformance']['error_code'], 'executable_not_found')

    def test_unexpected_errors_propagate(self):
        with patch.object(R.subprocess, 'run', side_effect=RuntimeError('unexpected')):
            for function, args in ((R.command_result, (['tool'],)), (R.git_commit, ()), (R.node_version, ())):
                with self.assertRaises(RuntimeError): function(*args)

    def test_nonzero_exit_stays_failure_and_optional_metadata_null(self):
        with patch.object(R.subprocess, 'run', return_value=subprocess.CompletedProcess([], 7, stdout='secret', stderr='secret')):
            self.assertEqual(R.command_result(['tool']), {'status':'FAIL','returncode':7})
            self.assertIsNone(R.git_commit())
            self.assertIsNone(R.node_version())

if __name__ == '__main__': unittest.main()
