"""Changed-job handoff invariants with labelled, non-inference fixtures.

A reviewed replacement is private untrusted code, not a merge certificate,
execution permission, or evidence that retained behavior is still correct.
"""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch


SPEC = importlib.util.spec_from_file_location(
    'job_resolution_workbench',
    Path(__file__).resolve().parents[1] / 'experiments/workbench.py')
W = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(W)

INTENT = 'Adjust target by one; preserve the helper and all other behavior.'
SOURCE = (
    '# private fixture source, not a live workload\n'
    'import math\n'
    'LIMIT = 5\n\n'
    'def helper(value):\n'
    '    return math.floor(value)\n\n'
    'def target(value):\n'
    '    return helper(value) + LIMIT\n\n'
    'def outside(value):\n'
    '    return value - 10\n'
)
RETAINED = 'def target(value):\n    return helper(value) + LIMIT + 1\n'
CURRENT = SOURCE.replace(
    '    return helper(value) + LIMIT\n',
    '    value = max(value, 0)\n    return helper(value) + LIMIT\n'
).replace('return value - 10', 'return value - 20')
RESOLVED = (
    'def target(value):\n'
    '    value = max(value, 0)\n'
    '    return helper(value) + LIMIT + 1\n'
)


class LabelledCompletionStub:
    """Deterministic fixture, not an inference backend or model result."""

    def __init__(self, text=None):
        self.text, self.calls = text, 0
        self.messages = []

    def complete(self, *args, **kwargs):
        self.calls += 1
        self.messages.append(args[0])
        if self.text is None:
            raise AssertionError('offline handoff must not request completion')
        return {'complete': True, 'text': self.text}


class JobResolutionTests(unittest.TestCase):
    def fixture(self, root, newline='\n', historical=False):
        source = root / 'source.py'
        source.write_bytes(SOURCE.replace('\n', newline).encode('utf-8'))
        creator = W.ProposalSession(LabelledCompletionStub(RETAINED))
        first = creator.propose({'file': str(source), 'symbol': 'target',
                                 'context_symbols': ['helper'], 'instruction': INTENT})
        self.assertTrue(first['reviewable'], first.get('rejection'))
        if historical:
            creator.proposals[first['proposal_id']]['executed_check'] = {
                'output_tail': 'old checks passed; not current authority',
                'plan_sha256': 'a' * 64,
            }
        capsule = root / 'retained.anvil-job.json'
        creator.save_job(first['proposal_id'], root, capsule)
        source.write_bytes(CURRENT.replace('\n', newline).encode('utf-8'))
        replacement = root / 'reviewed-function.py'
        replacement.write_bytes(RESOLVED.encode('utf-8'))
        backend = LabelledCompletionStub()
        runner = Mock(spec=['run', 'fresh_inputs'])
        runner.run.side_effect = AssertionError('handoff must not execute checks')
        runner.fresh_inputs.side_effect = AssertionError('old checks cannot become current')
        session = W.ProposalSession(backend, runner)
        return source, capsule, replacement, session, backend, runner

    def digest(self, source):
        return hashlib.sha256(source.read_bytes()).hexdigest()

    def assert_inert(self, result, backend, runner):
        self.assertEqual(result['model_requests'], 0)
        self.assertEqual(result['tests'], 'not_run')
        self.assertFalse(result['approved'])
        self.assertFalse(result['applied'])
        self.assertFalse(result['semantic_certificate'])
        self.assertEqual(backend.calls, 0)
        runner.run.assert_not_called()
        runner.fresh_inputs.assert_not_called()

    def resolve(self, source, capsule, replacement, session, instruction=INTENT, digest=None):
        return session.resolve_job(capsule, source.parent, instruction, replacement,
                                   self.digest(source) if digest is None else digest)

    def test_inspection_exposes_three_functions_without_creating_a_proposal(self):
        with tempfile.TemporaryDirectory() as directory:
            source, capsule, replacement, session, backend, runner = self.fixture(Path(directory))
            before = {path: path.read_bytes() for path in (source, capsule, replacement)}
            result = session.inspect_job(capsule, source.parent, INTENT)
            self.assertTrue(result['inspected'])
            self.assertTrue(result['selected_changed'])
            self.assertFalse(result['strict_resume_compatible'])
            self.assertTrue(result['blocking_reasons'])
            self.assertEqual(result['source_sha256'], self.digest(source))
            self.assertEqual(result['base_function'], W._job_function_span(SOURCE, 'target')[2])
            self.assertEqual(result['current_function'], W._job_function_span(CURRENT, 'target')[2])
            self.assertEqual(result['retained_function'], RETAINED)
            self.assertIsNone(result.get('proposal_id'))
            self.assertEqual(session.proposals, {})
            self.assert_inert(result, backend, runner)
            for path, raw in before.items():
                self.assertEqual(path.read_bytes(), raw)
            with self.assertRaises(ValueError):
                session.resume_job(capsule, source.parent, INTENT)

    def test_compatible_inspection_still_creates_neither_evidence_nor_proposal(self):
        with tempfile.TemporaryDirectory() as directory:
            source, capsule, _, session, backend, runner = self.fixture(Path(directory))
            source.write_bytes(SOURCE.encode('utf-8'))
            result = session.inspect_job(capsule, source.parent, INTENT)
            self.assertFalse(result['selected_changed'])
            self.assertTrue(result['strict_resume_compatible'])
            self.assertEqual(result['blocking_reasons'], [])
            self.assertEqual(session.proposals, {})
            self.assert_inert(result, backend, runner)

    def test_resolution_preserves_current_outside_bytes_and_drops_old_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            source, capsule, replacement, session, backend, runner = self.fixture(
                Path(directory), historical=True)
            original, saved = source.read_bytes(), capsule.read_bytes()
            result = self.resolve(source, capsule, replacement, session)
            self.assertTrue(result['resolved'])
            self.assertTrue(result['reviewable'])
            self.assertTrue(result['fresh_checks_required'])
            self.assertTrue(result['fresh_review_required'])
            self.assertEqual(result['source_sha256'], self.digest(source))
            self.assert_inert(result, backend, runner)
            proposal = session.proposals[result['proposal_id']]
            expected = CURRENT.replace('return helper(value) + LIMIT',
                                       'return helper(value) + LIMIT + 1')
            self.assertEqual(proposal['text'], expected)
            self.assertNotIn('executed_check', proposal)
            self.assertNotIn('test_report', proposal)
            self.assertEqual(session.check_status(result['proposal_id']),
                             {'tests': 'not_run', 'approved': False})
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(capsule.read_bytes(), saved)
            second = self.resolve(source, capsule, replacement, session)
            self.assertNotEqual(second['proposal_id'], result['proposal_id'])

    def test_resolution_keeps_current_crlf_boundary_and_unrelated_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            source, capsule, replacement, session, _, _ = self.fixture(Path(directory), '\r\n')
            # Imported function deliberately uses LF; only its final boundary
            # is canonicalized like an ordinary function proposal.
            replacement.write_bytes(RESOLVED.rstrip('\n').encode('utf-8'))
            result = self.resolve(source, capsule, replacement, session)
            candidate = session.proposals[result['proposal_id']]['text']
            start, end, _ = W._job_function_span(CURRENT.replace('\n', '\r\n'), 'target')
            self.assertEqual(candidate,
                             CURRENT.replace('\n', '\r\n')[:start] +
                             RESOLVED.rstrip('\n') + '\r\n' +
                             CURRENT.replace('\n', '\r\n')[end:])

    def test_helper_and_module_environment_changes_refuse_resolution(self):
        changes = (
            CURRENT.replace('return math.floor(value)', 'return math.ceil(value)'),
            CURRENT.replace('LIMIT = 5', 'LIMIT = 6'),
            CURRENT.replace('def outside(value):', 'def outside(value=1):'),
        )
        for changed in changes:
            with self.subTest(change=changed), tempfile.TemporaryDirectory() as directory:
                source, capsule, replacement, session, backend, runner = self.fixture(Path(directory))
                source.write_bytes(changed.encode('utf-8'))
                inspected = session.inspect_job(capsule, source.parent, INTENT)
                self.assertFalse(inspected['strict_resume_compatible'])
                self.assertTrue(inspected['blocking_reasons'])
                with self.assertRaises(ValueError):
                    self.resolve(source, capsule, replacement, session)
                self.assertEqual(session.proposals, {})
                self.assertEqual(backend.calls, 0)
                runner.run.assert_not_called()

    def test_stale_and_malformed_source_hashes_refuse_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            source, capsule, replacement, session, backend, _ = self.fixture(Path(directory))
            for digest in (hashlib.sha256(SOURCE.encode()).hexdigest(), '', '0' * 63,
                           'A' * 64, 'g' * 64, None, 4, True):
                with self.subTest(digest=digest), self.assertRaises((TypeError, ValueError)):
                    session.resolve_job(capsule, source.parent, INTENT, replacement, digest)
            self.assertEqual(session.proposals, {})
            self.assertEqual(backend.calls, 0)

    def test_explicit_exact_intent_is_required_for_inspection_and_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            source, capsule, replacement, session, backend, _ = self.fixture(Path(directory))
            for intent in (None, '', INTENT + ' ', 'Different task.'):
                with self.subTest(intent=intent):
                    with self.assertRaises(ValueError):
                        session.inspect_job(capsule, source.parent, intent)
                    with self.assertRaises(ValueError):
                        self.resolve(source, capsule, replacement, session, instruction=intent)
            self.assertEqual(session.proposals, {})
            self.assertEqual(backend.calls, 0)

    def test_invalid_extra_scope_and_no_op_replacements_are_refused(self):
        replacements = (
            'def renamed(value):\n    return value\n',
            RESOLVED + '\ndef second():\n    return 2\n',
            'LIMIT = 7\n' + RESOLVED,
            'def target(value):\n    return (\n',
            W._job_function_span(CURRENT, 'target')[2],
        )
        with tempfile.TemporaryDirectory() as directory:
            source, capsule, replacement, session, backend, _ = self.fixture(Path(directory))
            for text in replacements:
                replacement.write_bytes(text.encode('utf-8'))
                with self.subTest(text=text), self.assertRaises((ValueError, SyntaxError)):
                    self.resolve(source, capsule, replacement, session)
            self.assertEqual(session.proposals, {})
            self.assertEqual(backend.calls, 0)

    def test_oversized_non_utf8_and_outside_replacement_paths_are_refused(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            source, capsule, replacement, session, backend, _ = self.fixture(Path(directory))
            for raw in (b'x' * 32769, b'\xff', b'\x00' + RESOLVED.encode()):
                replacement.write_bytes(raw)
                with self.subTest(raw_length=len(raw)), self.assertRaises((ValueError, UnicodeError, SyntaxError)):
                    self.resolve(source, capsule, replacement, session)
            outer = Path(outside) / 'replacement.py'
            outer.write_bytes(RESOLVED.encode())
            with self.assertRaises(ValueError):
                self.resolve(source, capsule, outer, session)
            self.assertEqual(session.proposals, {})
            self.assertEqual(backend.calls, 0)

    def test_source_drift_during_replay_cannot_create_a_proposal(self):
        with tempfile.TemporaryDirectory() as directory:
            source, capsule, replacement, session, backend, _ = self.fixture(Path(directory))
            saved = capsule.read_bytes()
            replay = W._job_replay

            def drift(*args, **kwargs):
                result = replay(*args, **kwargs)
                source.write_bytes(source.read_bytes() + b'\n# concurrent edit during validation\n')
                return result

            with patch.object(W, '_job_replay', side_effect=drift), self.assertRaises(ValueError):
                self.resolve(source, capsule, replacement, session)
            self.assertEqual(session.proposals, {})
            self.assertEqual(backend.calls, 0)
            self.assertEqual(capsule.read_bytes(), saved)

    def test_malformed_capsule_refuses_inspection_and_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            source, capsule, replacement, session, _, _ = self.fixture(Path(directory))
            packet = capsule.read_bytes()
            capsule.write_bytes(packet[:-1] + b',"instruction":"different"}')
            for operation in ('inspect', 'resolve'):
                with self.subTest(operation=operation), self.assertRaises(ValueError):
                    if operation == 'inspect':
                        session.inspect_job(capsule, source.parent, INTENT)
                    else:
                        self.resolve(source, capsule, replacement, session)
            self.assertEqual(session.proposals, {})

    def test_offline_json_dispatch_supports_handoff_and_rejects_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            source, capsule, replacement, _, _, _ = self.fixture(Path(directory))
            common = {'project_root': str(source.parent), 'instruction': INTENT}
            inspection = dict(common, inspect_job=str(capsule))
            resolution = dict(common, resolve_job=str(capsule), replacement=str(replacement),
                              current_source_sha256=self.digest(source))
            requests = [json.dumps(inspection), json.dumps(resolution)]
            requests += [json.dumps(request)[:-1] + ',"instruction":"other task"}'
                         for request in (inspection, resolution)]
            before, saved = source.read_bytes(), capsule.read_bytes()
            with patch.object(W.sys, 'argv', ['workbench', '--backend', 'offline']), \
                    patch.object(W.sys, 'stdin', io.StringIO('\n'.join(requests) + '\n')), \
                    patch.object(W.sys, 'stdout', io.StringIO()) as output, \
                    patch.object(W.OfflineCompletion, 'complete',
                                 side_effect=AssertionError('offline JSON handoff must not infer')) as complete:
                W.main()
            replies = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertEqual(replies[0]['backend'], 'offline')
            self.assertEqual(len(replies), 5)
            self.assertTrue(replies[1]['inspected'])
            self.assertTrue(replies[2]['resolved'])
            for reply in replies[3:]:
                self.assertEqual(reply['error'], 'ValueError')
                self.assertIn('duplicate', reply['message'])
                self.assertFalse(reply['applied'])
            complete.assert_not_called()
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(capsule.read_bytes(), saved)


class JobReconciliationTests(unittest.TestCase):
    """Completion invocations below are deterministic stubs, never inference."""

    fixture = JobResolutionTests.fixture
    digest = JobResolutionTests.digest

    def reconcile(self, source, capsule, session, instruction=INTENT, digest=None, max_tokens=1024):
        return session.reconcile_job(capsule, source.parent, instruction,
                                     self.digest(source) if digest is None else digest, max_tokens)

    def test_one_draft_preserves_current_outside_bytes_and_imports_no_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            source, capsule, _, session, backend, runner = self.fixture(Path(directory), historical=True)
            backend.text = RESOLVED
            before, saved = source.read_bytes(), capsule.read_bytes()
            result = self.reconcile(source, capsule, session)
            self.assertTrue(result['reviewable'], result.get('rejection'))
            self.assertEqual(backend.calls, 1)
            self.assertEqual(result['completion_invocations'], 1)
            self.assertIsNone(result['model_requests'])  # Stub has no transport metrics.
            self.assertEqual(result['automatic_retries'], 0)
            self.assertFalse(result['approved'])
            self.assertFalse(result['applied'])
            self.assertFalse(result['semantic_certificate'])
            self.assertTrue(result['fresh_checks_required'])
            self.assertTrue(result['fresh_review_required'])
            self.assertEqual(session.check_status(result['proposal_id'])['tests'], 'not_run')
            proposal = session.proposals[result['proposal_id']]
            self.assertNotIn('executed_check', proposal)
            self.assertIsNone(proposal['original_instruction'])
            start, end, _ = W._job_function_span(CURRENT, 'target')
            self.assertEqual(proposal['text'], CURRENT[:start] + RESOLVED + CURRENT[end:])
            packet = json.loads(backend.messages[0][1]['content'])
            self.assertEqual(packet['current_request'], INTENT)
            self.assertEqual(packet['read_only_helpers'][0]['name'], 'helper')
            self.assertNotIn('old checks passed', str(packet))
            self.assertNotIn('def outside', str(packet))
            runner.run.assert_not_called()
            runner.fresh_inputs.assert_not_called()
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(capsule.read_bytes(), saved)

    def test_wrong_intent_stale_hash_or_invalid_budget_refuse_before_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            source, capsule, _, session, backend, _ = self.fixture(Path(directory))
            for kwargs in ({'instruction': 'another task'}, {'digest': 'a' * 64},
                           {'digest': 'invalid'}, {'max_tokens': 0}, {'max_tokens': True},
                           {'max_tokens': 4097}):
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    self.reconcile(source, capsule, session, **kwargs)
            self.assertEqual(backend.calls, 0)
            self.assertEqual(session.proposals, {})

    def test_unchanged_code_helpers_and_environment_use_existing_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            source, capsule, _, session, backend, _ = self.fixture(Path(directory))
            for current in (SOURCE, CURRENT.replace('math.floor(value)', 'math.ceil(value)'),
                            CURRENT.replace('LIMIT = 5', 'LIMIT = 6')):
                source.write_text(current, encoding='utf-8')
                with self.subTest(current=current), self.assertRaises(ValueError):
                    self.reconcile(source, capsule, session)
            self.assertEqual(backend.calls, 0)

    def test_refusal_bad_scope_header_and_incomplete_outputs_add_no_proposal(self):
        with tempfile.TemporaryDirectory() as directory:
            source, capsule, _, session, backend, _ = self.fixture(Path(directory))
            for text in ('ANVIL_UNRESOLVED', '```python\n' + RESOLVED + '```',
                         'def another(value):\n    return value\n',
                         RESOLVED + '\nLIMIT = 0\n',
                         RESOLVED.replace('target(value)', 'target(value, extra=1)'),
                         'def target(value):\n    return (\n',
                         'def target(value):\n    return "\ud800"\n'):
                backend.text = text
                with self.subTest(text=text):
                    result = self.reconcile(source, capsule, session)
                    self.assertFalse(result['reviewable'])
                    self.assertIsNone(result['proposal_id'])
                    self.assertTrue(result['rejection'])
                    self.assertEqual(result['unresolved'], text == 'ANVIL_UNRESOLVED')
            self.assertEqual(backend.calls, 7)
            with patch.object(backend, 'complete', return_value={'complete': False, 'text': RESOLVED}) as call:
                result = self.reconcile(source, capsule, session)
            self.assertFalse(result['reviewable'])
            call.assert_called_once()
            self.assertEqual(session.proposals, {})

    def test_source_and_capsule_changes_during_completion_discard_draft(self):
        for changed_input in ('source', 'capsule'):
            with self.subTest(changed_input=changed_input), tempfile.TemporaryDirectory() as directory:
                source, capsule, _, session, backend, _ = self.fixture(Path(directory))
                backend.text = RESOLVED
                complete = backend.complete

                def mutate(*args, **kwargs):
                    generated = complete(*args, **kwargs)
                    changed = source if changed_input == 'source' else capsule
                    changed.write_bytes(changed.read_bytes() + b'\n')
                    return generated

                with patch.object(backend, 'complete', side_effect=mutate):
                    result = self.reconcile(source, capsule, session)
                self.assertFalse(result['reviewable'])
                self.assertTrue(result[changed_input + '_changed'])
                self.assertEqual(backend.calls, 1)
                self.assertEqual(session.proposals, {})

    def test_crlf_boundaries_survive_model_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            source, capsule, _, session, backend, _ = self.fixture(Path(directory), newline='\r\n')
            backend.text = RESOLVED
            result = self.reconcile(source, capsule, session)
            self.assertTrue(result['reviewable'])
            candidate = session.proposals[result['proposal_id']]['text']
            start, end, _ = W._job_function_span(CURRENT.replace('\n', '\r\n'), 'target')
            self.assertEqual(candidate[:start], CURRENT.replace('\n', '\r\n')[:start])
            self.assertTrue(W._job_function_span(candidate, 'target')[2].endswith('\r\n'))
            self.assertTrue(candidate.endswith(CURRENT.replace('\n', '\r\n')[end:]))

    def test_prompt_limit_and_retained_header_changes_refuse_before_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            source, capsule, _, session, backend, _ = self.fixture(Path(directory))
            # Valid source but excessive combined escaped handoff context.
            large = '\n'.join('    # ' + 'x' * 80 for _ in range(310)) + '\n'
            packet = json.loads(capsule.read_bytes())
            packet['source_text'] = packet['source_text'].replace('def target(value):\n',
                                                               'def target(value):\n' + large)
            packet['text'] = packet['text'].replace('def target(value):\n',
                                                 'def target(value):\n' + large)
            for key, checksum in (('source_text', 'source_sha256'), ('text', 'replacement_sha256')):
                packet[checksum] = W.hashlib.sha256(packet[key].encode()).hexdigest()
            capsule.write_text(json.dumps(packet), encoding='utf-8')
            source.write_text(packet['source_text'].replace('    return helper(value) + LIMIT\n',
                              '    value = max(value, 0)\n    return helper(value) + LIMIT\n'), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'prompt exceeds'):
                self.reconcile(source, capsule, session)
            self.assertEqual(backend.calls, 0)
            packet['text'] = packet['text'].replace('target(value)', 'target(value, extra=1)')
            packet['replacement_sha256'] = W.hashlib.sha256(packet['text'].encode()).hexdigest()
            capsule.write_text(json.dumps(packet), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'retained signature'):
                self.reconcile(source, capsule, session)
            self.assertEqual(backend.calls, 0)

    def test_wrong_but_syntactically_valid_answer_is_not_a_semantic_certificate(self):
        with tempfile.TemporaryDirectory() as directory:
            source, capsule, _, session, backend, _ = self.fixture(Path(directory))
            backend.text = 'def target(value):\n    return 0\n'
            result = self.reconcile(source, capsule, session)
            self.assertTrue(result['reviewable'])  # Important retained negative boundary.
            self.assertFalse(result['semantic_certificate'])
            self.assertFalse(result['approved'])
            self.assertTrue(result['fresh_review_required'])

    def test_offline_and_json_duplicate_keys_make_no_completion_request(self):
        with tempfile.TemporaryDirectory() as directory:
            source, capsule, _, _, _, _ = self.fixture(Path(directory))
            request = {'reconcile_job': str(capsule), 'project_root': str(source.parent),
                       'instruction': INTENT, 'current_source_sha256': self.digest(source)}
            lines = [json.dumps(request), json.dumps(request)[:-1] + ',"instruction":"other"}']
            with patch.object(W.sys, 'argv', ['workbench', '--backend', 'offline']), \
                    patch.object(W.sys, 'stdin', io.StringIO('\n'.join(lines) + '\n')), \
                    patch.object(W.sys, 'stdout', io.StringIO()) as output, \
                    patch.object(W.OfflineCompletion, 'complete', side_effect=AssertionError('no inference')) as call:
                W.main()
            replies = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertEqual(replies[1]['error'], 'RuntimeError')
            self.assertEqual(replies[2]['error'], 'ValueError')
            self.assertIn('duplicate', replies[2]['message'])
            call.assert_not_called()

    def test_json_dispatch_uses_one_stub_completion_and_backend_failure_never_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            source, capsule, _, session, backend, runner = self.fixture(Path(directory))
            backend.text = RESOLVED
            request = {'reconcile_job': str(capsule), 'project_root': str(source.parent),
                       'instruction': INTENT, 'current_source_sha256': self.digest(source)}
            # Patch the backend constructor: there is no HTTP endpoint or model.
            with patch.object(W.SplashCompletion, '__new__', return_value=backend), \
                    patch.object(W.sys, 'argv', ['workbench', '--backend', 'splash',
                                               '--model', 'deterministic-fixture']), \
                    patch.object(W.sys, 'stdin', io.StringIO(json.dumps(request) + '\n')), \
                    patch.object(W.sys, 'stdout', io.StringIO()) as output:
                W.main()
            replies = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertTrue(replies[1]['reviewable'])
            self.assertEqual(backend.calls, 1)
            with patch.object(backend, 'complete', side_effect=RuntimeError('fixture backend failure')) as call:
                with self.assertRaises(RuntimeError):
                    self.reconcile(source, capsule, session)
                call.assert_called_once()
            self.assertEqual(session.proposals, {})
            runner.run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
