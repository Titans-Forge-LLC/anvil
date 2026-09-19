"""Dependency-free checks for the optional resident workbench."""
import importlib.util
import io
import json
from unittest.mock import patch
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    'workbench', Path(__file__).resolve().parents[1] / 'experiments/workbench.py')
W = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(W)


class Backend:
    context_limit = 4096
    eos_ids = {0}

    def __init__(self):
        self.fail = False

    def encode(self, tokens):
        return tokens

    def decode(self, tokens):
        return str(tokens)

    def new_cache(self):
        return []

    def offset(self, cache):
        return len(cache)

    def trim(self, cache, n):
        if n:
            del cache[-n:]

    def advance(self, tokens, cache):
        cache.extend(tokens)

    def forward(self, tokens, cache):
        out = []
        for token in tokens:
            cache.append(token)
            if self.fail:
                self.fail = False
                raise RuntimeError('injected error after KV mutation')
            pos = len(cache) - 2
            out.append(0 if pos == 40 else 100 + pos + (cache[1] % 2 if pos == 19 else 0))
        return out


class WorkbenchTests(unittest.TestCase):
    def test_cli_reads_bounded_lines_and_recovers_after_oversize(self):
        class BoundedInput(io.StringIO):
            def __iter__(self):
                raise AssertionError('unbounded iteration')
            def readline(self, size=-1):
                if not 0 < size <= 16385:
                    raise AssertionError('unbounded read')
                return super().readline(size)
        class Session:
            requests = []
            def __init__(self, completion):
                pass
            def propose(self, request):
                self.requests.append(request)
                return {'received': request, 'applied': False}
        maximum = '{}' + ' ' * (16384 - 3) + '\n'
        oversized = '{}' + ' ' * 50000 + '\n'
        # Review-derived boundary: this oversized line already includes its newline.
        exact_oversize = '{}' + ' ' * (16385 - 3) + '\n'
        data = maximum + oversized + '[1]\nnot json\n' + exact_oversize + '{"ok":1}\n' + '{"last":2}'
        output = io.StringIO()
        with patch.object(W.sys, 'argv', ['workbench', '--backend', 'splash']), \
             patch.object(W.sys, 'stdin', BoundedInput(data)), \
             patch.object(W.sys, 'stdout', output), \
             patch.object(W, 'SplashCompletion', return_value=object()), \
             patch.object(W, 'ProposalSession', Session):
            W.main()
        replies = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertTrue(replies[0]['ready'])
        self.assertEqual(Session.requests, [{}, {'ok': 1}, {'last': 2}])
        self.assertEqual(len(replies), 8)
        self.assertEqual(sum('error' in r for r in replies), 4)
        self.assertIn('16 KiB', replies[2]['message'])
        self.assertTrue(all(not r.get('applied', False) for r in replies))
        # Oversized unterminated final line emits exactly one error, then EOF.
        Session.requests = []
        output = io.StringIO()
        with patch.object(W.sys, 'argv', ['workbench', '--backend', 'splash']), \
             patch.object(W.sys, 'stdin', BoundedInput('x' * 50000)), \
             patch.object(W.sys, 'stdout', output), \
             patch.object(W, 'SplashCompletion', return_value=object()), \
             patch.object(W, 'ProposalSession', Session):
            W.main()
        self.assertEqual(len(output.getvalue().splitlines()), 2)
        self.assertEqual(Session.requests, [])

    def test_unchanged_proposals_not_retained_but_reverting_parent_is_valid(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.py'
            original = 'def f():\n    return 1\n'
            path.write_bytes(original.encode('utf-8'))
            class Complete:
                text = original
                def complete(self, messages, max_tokens):
                    return {'text': self.text, 'complete': True}
            c = Complete()
            session = W.ProposalSession(c)
            request = dict(file=str(path), symbol='f', instruction='Edit')
            for extra in ({}, {'symbol': None}):
                result = session.propose({**request, **extra})
                self.assertFalse(result['reviewable'])
                self.assertIn('unchanged', result['rejection'])
                self.assertIsNone(result['replacement_text'])
                self.assertIsNone(result['diff_preview'])
                self.assertIsNone(result['proposal_id'])
            self.assertEqual(len(session.proposals), 0)
            c.text = original.replace('1', '2')
            parent = session.propose(request)
            same = session.propose(dict(revise=parent['proposal_id'], instruction='Again'))
            self.assertFalse(same['reviewable'])
            self.assertEqual(len(session.proposals), 1)
            c.text = original
            revert = session.propose(dict(revise=parent['proposal_id'], instruction='Revert'))
            self.assertTrue(revert['reviewable'])
            self.assertEqual(revert['replacement_text'], original)
            # Two individually changing edits can cancel in the combined result.
            c.text = json.dumps({'edits': [{'old': 'return ', 'new': 'ret'},
                                         {'old': '1', 'new': 'urn 1'}]})
            result = session.propose({**request, 'format': 'edits'})
            self.assertFalse(result['reviewable'])
            self.assertIn('unchanged', result['rejection'])
            self.assertEqual(path.read_text(), original)

    def test_function_selection_uses_python_physical_lines(self):
        for separator in ('\u2028', '\u2029', '\x85', '\v', '\f'):
            for newline in ('\n', '\r\n', '\r'):
                with self.subTest(separator=repr(separator), newline=repr(newline)):
                    with tempfile.TemporaryDirectory() as directory:
                        path = Path(directory) / 'sample.py'
                        selected = f'def f():{newline}    # inside {separator} comment{newline}    return 1{newline}'
                        original = f'# before {separator} comment{newline}{selected}x = 3{newline}'
                        path.write_bytes(original.encode())
                        class Complete:
                            def complete(self, messages, max_tokens):
                                self.prompt = messages[1]['content']
                                return {'text': selected.replace('return 1', 'return 2'), 'complete': True}
                        c = Complete()
                        result = W.propose(c, {'file': str(path), 'symbol': 'f', 'instruction': 'Return 2'})
                        self.assertIn('SOURCE (verbatim):\n' + selected + '\nEND SOURCE', c.prompt)
                        self.assertTrue(result['reviewable'])
                        self.assertEqual(result['replacement_text'], original.replace('return 1', 'return 2'))
                        self.assertEqual(path.read_bytes(), original.encode())

    def test_first_request_source_draft_matches_target_after_mismatch(self):
        b = Backend()
        b.encode_text = lambda text: list(range(100, 140))
        c = W.Completion(b, source_drafts=True)
        result = c.complete([10, 1], draft_text='source')
        reference = W.Completion(Backend(), False).complete([10, 1])
        self.assertEqual(result['text'], reference['text'])
        self.assertEqual(result['draft_origin'], 'source')
        self.assertEqual(result['draft_tokens_verified'], 19)

    def test_source_draft_control_token_rejected_and_output_budget_honored(self):
        b = Backend()
        b.encode_text = lambda text: [100, 0, 101]
        c = W.Completion(b, source_drafts=True)
        result = c.complete([10, 1], draft_text='source')
        self.assertEqual(result['draft_origin'], 'none')
        self.assertEqual(result['draft_tokens_scored'], 0)
        b.encode_text = lambda text: list(range(100, 140))
        result = c.complete([10, 1], 3, draft_text='source')
        self.assertEqual(result['output_tokens'], 3)
        self.assertFalse(result['complete'])

    def test_revisions_use_parent_and_diff_against_disk_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.py'
            original = '# keep\ndef f():\n    return 1\n'
            path.write_bytes(original.encode('utf-8'))
            class Complete:
                text = 'def f():\n    return 2\n'
                def complete(self, messages, max_tokens):
                    self.prompt = messages[1]['content']
                    return {'text': self.text, 'complete': True}
            c = Complete()
            session = W.ProposalSession(c)
            first = session.propose({'file': str(path), 'symbol': 'f', 'instruction': 'Return 2'})
            c.text = 'def f():\n    return 3\n'
            second = session.propose({'revise': first['proposal_id'], 'instruction': 'Return 3 instead'})
            self.assertIn('return 2', c.prompt)
            self.assertIn('-    return 1', second['diff_preview'])
            self.assertIn('+    return 3', second['diff_preview'])
            self.assertEqual(second['replacement_text'], original.replace('return 1', 'return 3'))
            self.assertEqual(path.read_text(), original)
            self.assertEqual(second['parent_proposal_id'], first['proposal_id'])

    def test_revisions_reject_changed_source_unknown_parent_and_wrong_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.py'
            path.write_text('def f():\n    return 1\n')
            class Complete:
                calls = 0
                def complete(self, messages, max_tokens):
                    self.calls += 1
                    return {'text': 'def f():\n    return 2\n', 'complete': True}
            c = Complete()
            session = W.ProposalSession(c)
            first = session.propose({'file': str(path), 'symbol': 'f', 'instruction': 'Return 2'})
            for request in ({'revise': 'unknown'}, {'revise': first['proposal_id'], 'symbol': 'g'}):
                with self.assertRaises(ValueError):
                    session.propose({**request, 'instruction': 'Revise'})
            path.write_text('def f():\n    return 9\n')
            with self.assertRaisesRegex(ValueError, 'source changed'):
                session.propose({'revise': first['proposal_id'], 'instruction': 'Revise'})
            self.assertEqual(c.calls, 1)

    def test_proposal_retention_bounded_and_incomplete_not_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.py'
            path.write_text('x = 1\n')
            class Complete:
                finished = True
                def complete(self, messages, max_tokens):
                    return {'text': 'x = 2\n', 'complete': self.finished}
            c = Complete()
            session = W.ProposalSession(c)
            for _ in range(9):
                session.propose({'file': str(path), 'instruction': 'Change x'})
            self.assertEqual(len(session.proposals), 8)
            self.assertNotIn('p1', session.proposals)
            c.finished = False
            r = session.propose({'file': str(path), 'instruction': 'Change x'})
            self.assertIsNone(r['proposal_id'])
            self.assertEqual(len(session.proposals), 8)

    def test_named_function_preserves_surrounding_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.py'
            original = '# café\nimport math\n\ndef f():\n    return 1\n\n# keep\nx = 3\n'
            path.write_bytes(original.encode())
            class Complete:
                def complete(self, messages, max_tokens):
                    self.messages = messages
                    return {'text': 'def f():\n    return 2', 'complete': True}
            c = Complete()
            r = W.propose(c, {'file': str(path), 'symbol': 'f', 'instruction': 'Return 2'})
            self.assertTrue(r['reviewable'])
            self.assertEqual(r['replacement_text'], original.replace('return 1', 'return 2'))
            self.assertNotIn('import math', c.messages[1]['content'])
            self.assertEqual(path.read_bytes(), original.encode())

    def test_source_backslashes_are_not_json_escaped_in_model_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.py'
            source = 'def f():\n    return "\\n"\n'
            path.write_bytes(source.encode('utf-8'))
            class Complete:
                def complete(self, messages, max_tokens):
                    self.prompt = messages[1]['content']
                    return {'text': source, 'complete': True}
            c = Complete()
            W.propose(c, {'file': str(path), 'symbol': 'f', 'instruction': 'Keep behavior'})
            self.assertIn(source, c.prompt)

    def test_function_rejects_extra_statements_wrong_name_and_bad_syntax(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.py'
            path.write_text('def f():\n    return 1\n')
            class Complete:
                def complete(self, messages, max_tokens):
                    return {'text': self.text, 'complete': True}
            c = Complete()
            for text in ('def g():\n    return 2', 'def f():\n    return 2\nx=1', 'def f('):
                c.text = text
                r = W.propose(c, {'file': str(path), 'symbol': 'f', 'instruction': 'Return 2'})
                self.assertFalse(r['reviewable'])
                self.assertIsNone(r['replacement_text'])
            with self.assertRaises(ValueError):
                W.propose(c, {'file': str(path), 'symbol': 'missing', 'instruction': 'Return 2'})

    def test_block_mismatch_rollback_and_full_acceptance_match_ordinary(self):
        draft, ordinary = W.Completion(Backend()), W.Completion(Backend(), False)
        for prompt in ([10, 1], [10, 2], [10, 4], [10, 1]):
            a, b = draft.complete(prompt), ordinary.complete(prompt)
            self.assertEqual(a['text'], b['text'])
            self.assertTrue(a['complete'])
            if prompt == [10, 2]:
                self.assertEqual(a['draft_tokens_verified'], 19)
            if prompt == [10, 4]:
                self.assertEqual(a['draft_tokens_verified'], 41)

    def test_exact_hit_has_no_forward_work(self):
        c = W.Completion(Backend())
        c.complete([10, 1])
        result = c.complete([10, 1])
        self.assertTrue(result['exact_hit'])
        self.assertEqual(result['model_calls'], 0)

    def test_output_limit_is_in_exact_identity(self):
        c = W.Completion(Backend())
        c.complete([10, 1])
        short = c.complete([10, 1], 3)
        self.assertFalse(short['exact_hit'])
        self.assertFalse(short['complete'])
        self.assertEqual(short['output_tokens'], 3)

    def test_incomplete_output_never_cached_as_complete(self):
        c = W.Completion(Backend())
        c.complete([10, 1], 3)
        self.assertEqual(c.last, [])
        self.assertEqual(len(c.responses), 0)

    def test_backend_error_discards_mutated_state_and_recovers(self):
        b = Backend()
        c = W.Completion(b)
        b.fail = True
        with self.assertRaises(RuntimeError):
            c.complete([10, 1])
        self.assertIsNone(c.cache)
        self.assertTrue(c.complete([10, 1])['complete'])

    def test_reject_invalid_budget(self):
        for value in (0, -1, True, 4097):
            with self.assertRaises(ValueError):
                W.Completion(Backend()).complete([10, 1], value)

    def test_position_corruption_discards_cache(self):
        c = W.Completion(Backend())
        c.complete([10, 1])
        c.cache.append(999)
        with self.assertRaises(RuntimeError):
            c.complete([10, 2])
        self.assertIsNone(c.cache)

    def test_proposals_never_write_and_stale_source_blocks_diff(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.py'
            path.write_text('x = 1\n')
            class Complete:
                stale = False
                def complete(self, messages, max_tokens):
                    if self.stale:
                        path.write_text('x = 3\n')
                    return {'text': 'x = 2\n', 'complete': True}
            c = Complete()
            request = {'file': str(path), 'instruction': 'Change x to 2'}
            result = W.propose(c, request)
            self.assertTrue(result['reviewable'])
            self.assertIn('+x = 2', result['diff_preview'])
            self.assertFalse(result['applied'])
            self.assertEqual(path.read_text(), 'x = 1\n')
            c.stale = True
            result = W.propose(c, request)
            self.assertTrue(result['source_changed'])
            self.assertFalse(result['reviewable'])
            self.assertIsNone(result['diff_preview'])


if __name__ == '__main__':
    unittest.main()
