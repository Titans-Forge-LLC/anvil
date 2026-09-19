"""Dependency-free checks for the optional resident workbench."""
import importlib.util
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
