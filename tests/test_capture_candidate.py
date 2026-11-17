import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from anvil_workbench import capture_candidate as C, jobs
from anvil_workbench.workbench import ProposalSession, OfflineCompletion

class CaptureTests(unittest.TestCase):
    def case(self, root):
        source='def helper():\n    return 2\n\ndef target():\n    return helper()\n\ndef other():\n    return 7\n'
        candidate=source.replace('return helper()','return helper() + 1')
        (root/'a.py').write_bytes(source.encode('utf-8'))
        (root/'candidate.py').write_bytes(candidate.encode('utf-8'))
        (root/'intent.txt').write_text('Return helper plus one; preserve other behavior.')
        return source,candidate,hashlib.sha256(source.encode()).hexdigest()

    def capture(self, root, digest, **changes):
        args=dict(project_root=root,source_file='a.py',candidate_file='candidate.py',symbol='target',
                  intent_file='intent.txt',output='job.json',expected_source_sha256=digest,
                  context_symbols=['helper']);args.update(changes)
        return C.capture(**args)

    def test_capture_then_existing_resume_without_model_or_restored_success(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source,candidate,digest=self.case(root)
            with patch.object(OfflineCompletion,'complete',side_effect=AssertionError('model called')):
                result=self.capture(root,digest)
                self.assertEqual(result['tests'],'not_run');self.assertFalse(result['applied'])
                self.assertFalse(result['approved']);self.assertEqual(result['model_requests'],0)
                packet=json.loads((root/'job.json').read_text());self.assertIsNone(packet['historical_notes'])
                session=ProposalSession(OfflineCompletion())
                restored=session.resume_job(root/'job.json',root,(root/'intent.txt').read_text())
                self.assertEqual(restored['replacement_text'],candidate)
                self.assertEqual(restored['tests'],'not_run')
                self.assertEqual((root/'a.py').read_text(),source)

    def test_unrelated_current_work_survives_and_helpers_are_guarded(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source,_,digest=self.case(root);self.capture(root,digest)
            (root/'a.py').write_bytes(source.replace('return 7','return 8').encode('utf-8'))
            result=jobs.inspect_jobs(root,'intent.txt',['job.json'],export_patch='resume.patch')
            self.assertTrue(result['exported']);self.assertFalse(result['blocked'])
            (root/'a.py').write_bytes(source.replace('return 2','return 9').encode('utf-8'))
            result=jobs.inspect_jobs(root,'intent.txt',['job.json'],export_patch='blocked.patch')
            self.assertTrue(result['blocked']);self.assertFalse((root/'blocked.patch').exists())

    def test_stale_source_and_out_of_scope_candidate_are_refused(self):
        for fault in ('hash','scope','signature','no_change'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as d:
                root=Path(d);source,candidate,digest=self.case(root)
                if fault=='hash':digest='0'*64
                elif fault=='scope':(root/'candidate.py').write_bytes(candidate.replace('return 7','return 9').encode('utf-8'))
                elif fault=='signature':(root/'candidate.py').write_bytes(candidate.replace('def target():','def target(x):').encode('utf-8'))
                else:(root/'candidate.py').write_bytes(source.encode('utf-8'))
                with self.assertRaises(ValueError):self.capture(root,digest)
                self.assertFalse((root/'job.json').exists())

    def test_invalid_paths_and_existing_capsule_remain_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);_,_,digest=self.case(root)
            for changes in ({'source_file':'../a.py'},{'candidate_file':'/tmp/candidate.py'},
                            {'output':'../escape.json'},{'candidate_file':'a.py'}):
                with self.subTest(changes=changes),self.assertRaises((ValueError,OSError)):
                    self.capture(root,digest,**changes)
            (root/'job.json').write_text('keep')
            with self.assertRaises(FileExistsError):self.capture(root,digest)
            self.assertEqual((root/'job.json').read_text(),'keep')

    def test_changed_intent_during_validation_refuses_without_capsule(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);_,_,digest=self.case(root);original=C._job_replay
            def drift(*args):
                result=original(*args);(root/'intent.txt').write_text('changed');return result
            with patch.object(C,'_job_replay',side_effect=drift),self.assertRaisesRegex(ValueError,'changed during'):
                self.capture(root,digest)
            self.assertFalse((root/'job.json').exists())

    def test_cli_smoke_and_no_success_claim_for_failed_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source,_,digest=self.case(root)
            (root/'candidate.py').write_bytes(source.replace('return helper()','return -999').encode('utf-8'))
            command=[sys.executable,'-B','-m','anvil_workbench.capture_candidate','--project-root',str(root),
                '--source','a.py','--candidate','candidate.py','--symbol','target','--intent-file','intent.txt',
                '--output','job.json','--source-sha256',digest,'--context-symbol','helper']
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['tests'],'not_run')
            self.assertIsNone(json.loads((root/'job.json').read_text())['historical_notes'])
            self.assertEqual((root/'a.py').read_text(),source)

if __name__=='__main__':unittest.main()
