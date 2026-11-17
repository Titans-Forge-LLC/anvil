"""Offline recovery behavior, with labelled fixtures rather than model results."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from anvil_workbench import jobs
from anvil_workbench.workbench import ProposalSession


class FixedFixture:
    def complete(self, *args, **kwargs):
        return {'complete': True, 'text': 'def target():\n    return helper() + 1\n'}


class JobCommandTests(unittest.TestCase):
    def case(self, root, filenames=('a.py', 'b.py')):
        instruction = 'Return helper plus one; retain unrelated current work.'
        (root / 'task.txt').write_text(instruction, encoding='utf-8')
        caps, replacements = [], {}
        for index, filename in enumerate(filenames):
            source = root / filename
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b'def helper():\n    return 2\n\ndef target():\n    return helper()\n\n'
                               b'def outside():\n    return 7\n')
            creator = ProposalSession(FixedFixture())
            first = creator.propose(dict(file=str(source), symbol='target', context_symbols=['helper'],
                                          instruction=instruction))
            self.assertTrue(first['reviewable'])
            capsule = root / ('draft-' + str(index) + '.json')
            creator.save_job(first['proposal_id'], root, capsule)
            caps.append(capsule.name)
            replacements[filename] = first['replacement_text']
        return caps, replacements

    def test_mixed_status_is_private_read_only_and_does_not_restore_tests(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); caps, replacements = self.case(root)
            (root / 'a.py').write_bytes(replacements['a.py'].encode('utf-8'))
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            result = jobs.inspect_jobs(root, 'task.txt', caps)
            self.assertEqual([row['status'] for row in result['items']], ['already_present', 'pending'])
            self.assertFalse(result['blocked'])
            self.assertFalse(result['exported'])
            self.assertFalse(result['applied'])
            self.assertFalse(result['approved'])
            self.assertEqual(result['model_requests'], 0)
            self.assertEqual(result['tests'], 'not_run')
            self.assertNotIn('Return helper plus one', json.dumps(result))
            self.assertNotIn('def target', json.dumps(result))
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})

    @unittest.skipUnless(shutil.which('git'), 'Git is required for this patch-compatibility test')
    def test_exports_only_pending_edits_as_a_real_git_patch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); caps, replacements = self.case(root, ('a.py', 'folder/b space-é.py'))
            (root / 'a.py').write_bytes(replacements['a.py'].encode('utf-8'))
            result = jobs.inspect_jobs(root, 'task.txt', caps, export_patch='recovery.patch')
            self.assertTrue(result['exported'])
            patch_bytes = (root / 'recovery.patch').read_bytes()
            self.assertNotIn(b'a/a.py', patch_bytes)
            subprocess.run(['git', 'apply', '--check', 'recovery.patch'], cwd=root, check=True, capture_output=True)
            subprocess.run(['git', 'apply', 'recovery.patch'], cwd=root, check=True, capture_output=True)
            self.assertEqual((root / 'folder/b space-é.py').read_text(encoding='utf-8'), replacements['folder/b space-é.py'])
            if os.name != 'nt':
                self.assertEqual(stat.S_IMODE((root / 'recovery.patch').stat().st_mode), 0o600)

    def test_all_present_creates_no_empty_patch_and_still_requires_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); caps, replacements = self.case(root)
            for name, text in replacements.items():
                (root / name).write_bytes(text.encode('utf-8'))
            result = jobs.inspect_jobs(root, 'task.txt', caps, export_patch='unused.patch')
            self.assertEqual(result['already_present_files'], 2)
            self.assertTrue(result['fresh_checks_required'])
            self.assertFalse((root / 'unused.patch').exists())

    def test_one_conflict_blocks_combined_export_without_hiding_pending_work(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); caps, _ = self.case(root)
            source = root / 'a.py'
            source.write_bytes(source.read_bytes().replace(b'return helper()', b'return helper() + 9'))
            result = jobs.inspect_jobs(root, 'task.txt', caps, export_patch='blocked.patch')
            self.assertEqual([row['status'] for row in result['items']], ['conflicting', 'pending'])
            self.assertTrue(result['blocked'])
            self.assertFalse((root / 'blocked.patch').exists())

    def test_present_function_with_changed_helper_requires_reassessment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); caps, replacements = self.case(root)
            (root / 'a.py').write_bytes(replacements['a.py'].replace('return 2', 'return 3').encode('utf-8'))
            result = jobs.inspect_jobs(root, 'task.txt', caps, export_patch='blocked.patch')
            self.assertEqual(result['items'][0]['status'], 'reassess_dependencies')
            self.assertTrue(result['blocked'])
            self.assertFalse((root / 'blocked.patch').exists())

    def test_invalid_intent_capsule_and_duplicate_sources_refuse_export(self):
        for fault in ('intent', 'corrupt', 'duplicate_capsule', 'duplicate_source'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); caps, _ = self.case(root)
                if fault == 'intent': (root / 'task.txt').write_text('Different current task.', encoding='utf-8')
                elif fault == 'corrupt': (root / caps[1]).write_text('{"schema":"wrong"}', encoding='utf-8')
                elif fault == 'duplicate_capsule': caps = [caps[0], caps[0]]
                else:
                    (root / 'copy.json').write_bytes((root / caps[0]).read_bytes());caps = [caps[0], 'copy.json']
                with self.assertRaises(ValueError): jobs.inspect_jobs(root, 'task.txt', caps, export_patch='blocked.patch')
                self.assertFalse((root / 'blocked.patch').exists())

    def test_paths_cannot_escape_and_existing_export_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'project';root.mkdir();caps, _ = self.case(root)
            for output in ('../outside.patch',):
                with self.assertRaises(ValueError): jobs.inspect_jobs(root, 'task.txt', caps, export_patch=output)
            (root / 'exists.patch').write_bytes(b'keep')
            with self.assertRaises(FileExistsError): jobs.inspect_jobs(root, 'task.txt', caps, export_patch='exists.patch')
            self.assertEqual((root / 'exists.patch').read_bytes(), b'keep')
            (root.parent / 'intent.txt').write_bytes((root / 'task.txt').read_bytes())
            with self.assertRaises(ValueError): jobs.inspect_jobs(root, '../intent.txt', caps)
            (root / 'subdir').mkdir()
            result = jobs.inspect_jobs(root, 'task.txt', caps, export_patch='subdir/../normalized.patch')
            self.assertEqual(result['output'], 'normalized.patch')
            self.assertTrue((root / 'normalized.patch').is_file())

    def test_export_requires_same_capsule_identity_during_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            caps, _ = self.case(root)
            resume = ProposalSession.resume_job

            def mismatched_resume(session, *args):
                return dict(resume(session, *args), capsule_sha256='0' * 64)

            with patch.object(ProposalSession, 'resume_job', mismatched_resume):
                with self.assertRaisesRegex(ValueError, 'capsule changed'):
                    jobs.inspect_jobs(root, 'task.txt', caps, export_patch='blocked.patch')
            self.assertFalse((root / 'blocked.patch').exists())

    def test_changed_input_before_export_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); caps, _ = self.case(root)
            original = jobs._patch
            def drift(*args):
                (root / 'task.txt').write_text('Changed while preparing.', encoding='utf-8')
                return original(*args)
            with patch.object(jobs, '_patch', side_effect=drift):
                with self.assertRaisesRegex(ValueError, 'input changed'):
                    jobs.inspect_jobs(root, 'task.txt', caps, export_patch='blocked.patch')
            self.assertFalse((root / 'blocked.patch').exists())

    def test_source_drift_during_export_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); caps, _ = self.case(root)
            original = jobs._patch
            def drift(*args):
                with (root / 'a.py').open('a', encoding='utf-8') as stream: stream.write('# intervening edit\n')
                return original(*args)
            with patch.object(jobs, '_patch', side_effect=drift):
                with self.assertRaisesRegex(ValueError, 'input changed'):
                    jobs.inspect_jobs(root, 'task.txt', caps, export_patch='blocked.patch')
            self.assertFalse((root / 'blocked.patch').exists())

    def test_cli_human_and_json_status_and_blocked_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary);caps, _ = self.case(root)
            args = ['--project-root', str(root), '--intent-file', 'task.txt'] + caps
            output = io.StringIO()
            with contextlib.redirect_stdout(output): self.assertEqual(jobs.main(args), 0)
            self.assertIn('pending: "a.py"', output.getvalue())
            source = root / 'a.py'
            source.write_bytes(source.read_bytes().replace(b'return helper()', b'return 9'))
            output = io.StringIO()
            with contextlib.redirect_stdout(output): self.assertEqual(jobs.main(['--json'] + args), 2)
            result = json.loads(output.getvalue())
            self.assertTrue(result['blocked'])
            self.assertEqual(result['model_requests'], 0)

    def test_capsule_count_and_intent_byte_bounds(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary);caps, _ = self.case(root)
            for bad in ([], caps * 9, 'not-a-list'):
                with self.assertRaises(ValueError): jobs.inspect_jobs(root, 'task.txt', bad)
            (root / 'task.txt').write_bytes(b'x' * 16385)
            with self.assertRaises(ValueError): jobs.inspect_jobs(root, 'task.txt', caps)

    def test_patch_handles_missing_final_newline(self):
        value = jobs._patch('a.py', b'def value():\n    return 1', b'def value():\n    return 2')
        self.assertEqual(value.count(b'\\ No newline at end of file\n'), 2)


if __name__ == '__main__':
    unittest.main()
