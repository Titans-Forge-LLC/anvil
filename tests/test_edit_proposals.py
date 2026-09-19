import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('edit_workbench', Path(__file__).resolve().parents[1] / 'experiments/workbench.py')
W = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(W)


class Completion:
    def __init__(self, text, complete=True, mutate=None):
        self.text, self.finished, self.mutate = text, complete, mutate
        self.calls = 0

    def complete(self, messages, max_tokens):
        self.calls += 1
        if self.mutate:
            self.mutate()
        return {'text': self.text, 'complete': self.finished}


class EditTests(unittest.TestCase):
    def test_atomic_edits_use_original_snapshot_independent_of_order(self):
        edits = [{'old': 'abc', 'new': 'XYZ'}, {'old': 'XYZ', 'new': 'abc'}]
        for order in (edits, edits[::-1]):
            self.assertEqual(W.reconstruct_edit('abc---XYZ', json.dumps({'edits': order}),
                                                multiple=True), 'XYZ---abc')
        self.assertEqual(W.reconstruct_edit('ab', json.dumps({'edits': [
            {'old': 'a', 'new': ''}, {'old': 'b', 'new': 'B'}]}), multiple=True), 'B')

    def test_atomic_edits_reject_overlap_cascade_and_bad_envelopes(self):
        for edits in ([], [{'old': 'ab', 'new': 'X'}, {'old': 'bc', 'new': 'Y'}],
                      [{'old': 'a', 'new': 'X'}, {'old': 'a', 'new': 'Y'}],
                      [{'old': 'a', 'new': 'X'}, {'old': 'X', 'new': 'Y'}],
                      [{'old': 'a', 'new': 'X'}] * 17, {}, [None]):
            with self.subTest(edits=edits), self.assertRaises(ValueError):
                W.reconstruct_edit('abc', json.dumps({'edits': edits}), multiple=True)
        for envelope in ('{"edits":[],"edits":[]}', '{"edits":[{"old":"a","old":"b","new":"c"}]}',
                         '{"old":"a","new":"b"}', '{"edits":[],"extra":1}'):
            with self.assertRaises(ValueError):
                W.reconstruct_edit('abc', envelope, multiple=True)

    def test_atomic_proposal_revision_and_all_or_nothing_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.py'
            raw = b'# keep\r\ndef f():\r\n    a = 1\r\n    return a\r\nx = 3\r\n'
            path.write_bytes(raw)
            c = Completion(json.dumps({'edits': [{'old': 'a = 1', 'new': 'b = 2'},
                                                {'old': 'return a', 'new': 'return b'}]}))
            session = W.ProposalSession(c)
            request = dict(file=str(path), symbol='f', instruction='Edit', format='edits')
            first = session.propose(request)
            self.assertTrue(first['reviewable'])
            self.assertEqual(first['replacement_text'].encode(),
                             raw.replace(b'a = 1', b'b = 2').replace(b'return a', b'return b'))
            c.text = json.dumps({'edits': [{'old': 'b = 2', 'new': 'b = 4'}]})
            revised = session.propose(dict(revise=first['proposal_id'], instruction='Again'))
            self.assertEqual(revised['format'], 'edits')
            self.assertTrue(revised['reviewable'])
            for bad in ('absent', 'x = 3'):
                c.text = json.dumps({'edits': [{'old': 'a = 1', 'new': 'a = 2'},
                                              {'old': bad, 'new': 'x = 4'}]})
                result = session.propose(request)
                self.assertFalse(result['reviewable'])
                self.assertIsNone(result['replacement_text'])
            self.assertEqual(path.read_bytes(), raw)

    def test_exact_unicode_crlf_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.py'
            raw = '# café\r\ndef f():\r\n    return "é"\r\n\r\nx = 1\r\n'.encode()
            path.write_bytes(raw)
            c = Completion(json.dumps({'old': '"é"', 'new': '"猫"'}))
            result = W.propose(c, dict(file=str(path), symbol='f', instruction='Change value', format='edit'))
            self.assertTrue(result['reviewable'])
            self.assertEqual(result['replacement_text'].encode(), raw.replace('"é"'.encode(), '"猫"'.encode()))
            self.assertEqual(path.read_bytes(), raw)
            self.assertFalse(result['applied'])

    def test_reject_invalid_or_ambiguous_envelopes(self):
        for text in ('{}', '[]', '{"old":"a","new":"b","extra":1}',
                     '{"old":"a","old":"b","new":"c"}',
                     '{"old":"","new":"b"}', '{"old":"a","new":null}',
                     '{"old":"a","new":"a"}', '{"old":"x","new":"b"}',
                     '{"old":"aa","new":"b"}', '{"old":"a","new":"\\u0000"}',
                     '```json\n{}\n```', '{"old":"aaa","new":"\\ud800"}'):
            with self.subTest(text=text), self.assertRaises((ValueError, UnicodeError)):
                W.reconstruct_edit('aaa', text)

    def test_insertion_deletion_and_size(self):
        self.assertEqual(W.reconstruct_edit('abc', '{"old":"b","new":"bx"}'), 'abxc')
        self.assertEqual(W.reconstruct_edit('abc', '{"old":"b","new":""}'), 'ac')
        with self.assertRaises(ValueError):
            W.reconstruct_edit('x', json.dumps({'old': 'x', 'new': 'a' * 32769}))

    def test_edit_cannot_join_or_comment_out_following_module_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.py'
            for newline in ('\n', '\r\n', '\r'):
                with self.subTest(newline=repr(newline)):
                    raw = f'def f(): return 1{newline}x = 2{newline}'.encode()
                    path.write_bytes(raw)
                    c = Completion(json.dumps({'old': 'return 1' + newline, 'new': 'return 1 #'}))
                    result = W.propose(c, dict(file=str(path), symbol='f', format='edit', instruction='Edit'))
                    self.assertFalse(result['reviewable'])
                    self.assertIn('newline boundary', result['rejection'])
                    self.assertIsNone(result['replacement_text'])
                    self.assertEqual(path.read_bytes(), raw)

    def test_scope_syntax_truncation_and_stale_rejections(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.py'
            raw = b'def f():\n    return 1\n\nx = 1\n'
            for old, new, finished, mutate in (
                ('return 1', 'return (', True, False),
                ('f()', 'g()', True, False),
                ('return 1', 'return 2\n\ndef g():\n    pass', True, False),
                ('x = 1', 'x = 2', True, False),
                ('return 1', 'return 2', False, False),
                ('return 1', 'return 2', True, True),
            ):
                path.write_bytes(raw)
                c = Completion(json.dumps({'old': old, 'new': new}), finished,
                               (lambda: path.write_bytes(raw + b'# changed\n')) if mutate else None)
                result = W.propose(c, dict(file=str(path), symbol='f', format='edit', instruction='Edit'))
                self.assertFalse(result['reviewable'])
                self.assertIsNone(result['replacement_text'])
                self.assertIsNone(result['diff_preview'])

    def test_revision_inherits_format_and_binds_reconstructed_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.py'
            path.write_bytes(b'def f():\n    return 1\n')
            c = Completion('{"old":"return 1","new":"return 2"}')
            session = W.ProposalSession(c)
            first = session.propose(dict(file=str(path), symbol='f', instruction='Edit', format='edit'))
            c.text = '{"old":"return 2","new":"return 3"}'
            second = session.propose(dict(revise=first['proposal_id'], instruction='Again'))
            self.assertTrue(second['reviewable'])
            self.assertEqual(second['format'], 'edit')
            self.assertNotEqual(first['base_sha256'], second['base_sha256'])
            self.assertEqual(first['source_sha256'], second['source_sha256'])
            self.assertIn('return 3', second['replacement_text'])
            path.write_bytes(b'# changed\n')
            with self.assertRaises(ValueError):
                session.propose(dict(revise=second['proposal_id'], instruction='Again'))
            self.assertEqual(c.calls, 2)

    def test_missing_symbol_or_bad_format_rejected_before_inference(self):
        c = Completion('{}')
        for request in ({'format': 'edit'}, {'format': 'unknown'}):
            with self.assertRaises(ValueError):
                W.propose(c, request)
        c.source_drafts = True
        with self.assertRaises(ValueError):
            W.propose(c, dict(format='edit', symbol='f'))
        self.assertEqual(c.calls, 0)


if __name__ == '__main__':
    unittest.main()
