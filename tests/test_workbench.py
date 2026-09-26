"""Dependency-free checks for the optional resident workbench."""
import importlib.util
import io
import json
import shutil
import subprocess
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
    def test_interactive_selects_function_and_exports_only_on_request(self):
        class Complete:
            calls = 0
            def complete(self, *args, **kwargs):
                self.calls += 1
                return dict(text='def f():\n    return 2\n', complete=True)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'sample.py'
            original = b'def f():\n    return 1\n\ndef g():\n    return 3\n'
            path.write_bytes(original)
            client = Complete()
            session = W.ProposalSession(client)
            answers = 'sample.py\n1\n\nUse two\n\ne\nreview.patch\nq\n'
            with patch.object(W.sys, 'stdin', io.StringIO(answers)), \
                 patch.object(W.sys, 'stdout', io.StringIO()) as output:
                W.run_interactive(session, root)
            self.assertEqual(client.calls, 1)
            self.assertEqual(path.read_bytes(), original)
            self.assertTrue((root / 'review.patch').exists())
            self.assertIn('Nothing was applied or executed', output.getvalue())
            self.assertIn('proposal: p1', output.getvalue())

    def test_interactive_backend_failure_recovers_without_automatic_retry(self):
        class Complete:
            calls = 0
            def complete(self, *args, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError('private server detail must not be printed')
                return dict(text='def f():\n    return 2\n', complete=True)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'sample.py'
            original = b'def f():\n    return 1\n'
            source.write_bytes(original)
            for answers, expected_calls in [
                ('sample.py\n0\nUse two\n\n', 1),
                ('sample.py\n0\nUse two\nsample.py\n0\nUse two\nq\n', 2),
            ]:
                client = Complete()
                with patch.object(W.sys, 'stdin', io.StringIO(answers)), \
                     patch.object(W.sys, 'stdout', io.StringIO()) as output:
                    W.run_interactive(W.ProposalSession(client), root)
                self.assertEqual(client.calls, expected_calls)
                self.assertEqual(source.read_bytes(), original)
                self.assertEqual(list(root.iterdir()), [source])
                self.assertIn('Model request failed', output.getvalue())
                self.assertNotIn('private server detail', output.getvalue())
                if expected_calls == 2:
                    self.assertIn('Reviewable: True', output.getvalue())

    def test_interactive_rejects_path_escape_before_model(self):
        class Complete:
            calls = 0
            def complete(self, *args, **kwargs):
                self.calls += 1
                raise AssertionError('model should not run')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'root'
            root.mkdir()
            (root.parent / 'outside.py').write_text('def f(): pass\n')
            client = Complete()
            with patch.object(W.sys, 'stdin', io.StringIO('../outside.py\n\n')), \
                 patch.object(W.sys, 'stdout', io.StringIO()) as output:
                W.run_interactive(W.ProposalSession(client), root)
            self.assertEqual(client.calls, 0)
            self.assertIn('ValueError', output.getvalue())

    def test_interactive_revision_stays_source_bound(self):
        class Complete:
            calls = 0
            def complete(self, *args, **kwargs):
                self.calls += 1
                return dict(text=f'def f():\n    return {self.calls + 1}\n', complete=True)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'sample.py'
            original = b'def f():\n    return 1\n'
            path.write_bytes(original)
            client = Complete()
            answers = 'sample.py\n1\n\nUse two\n\nr\nUse three\nq\n'
            with patch.object(W.sys, 'stdin', io.StringIO(answers)), \
                 patch.object(W.sys, 'stdout', io.StringIO()) as output:
                W.run_interactive(W.ProposalSession(client), root)
            self.assertEqual(client.calls, 2)
            self.assertEqual(path.read_bytes(), original)
            self.assertIn('proposal: p2', output.getvalue())

    def test_patch_export_applies_exact_bytes_without_model_calls(self):
        git = shutil.which('git')
        if not git:
            self.skipTest('git is required for patch interoperability')
        class Complete:
            calls = 0
            def complete(self, *args, **kwargs):
                self.calls += 1
                return dict(text=self.text, complete=True)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run([git, 'init', '-q', str(root)], check=True, capture_output=True)
            path = root / 'module é space.py'
            client = Complete()
            for newline in ('\n', '\r\n', ''):
                with self.subTest(newline=repr(newline)):
                    original = ('def f():\n    return "é\u2028one"' + newline).encode()
                    path.write_bytes(original)
                    session = W.ProposalSession(client)
                    client.text = 'def f():\n    return "é\u2028two"' + newline
                    first = session.propose(dict(file=str(path), symbol='f', instruction='Use two'))
                    client.text = 'def f():\n    return "é\u2028three"' + newline
                    final = session.propose(dict(revise=first['proposal_id'], instruction='Use three'))
                    before = client.calls
                    output = root / ('export-' + str(len(newline)) + '.patch')
                    receipt = session.export_patch(final['proposal_id'], root, output)
                    self.assertEqual(client.calls, before)
                    self.assertFalse(receipt['applied'])
                    self.assertEqual(path.read_bytes(), original)
                    self.assertEqual(receipt['patch_sha256'], W.hashlib.sha256(output.read_bytes()).hexdigest())
                    subprocess.run([git, '-c', 'core.autocrlf=false', 'apply', '--check', str(output)], cwd=root, check=True, capture_output=True)
                    subprocess.run([git, '-c', 'core.autocrlf=false', 'apply', str(output)], cwd=root, check=True, capture_output=True)
                    self.assertEqual(path.read_bytes(), final['replacement_text'].encode())

    def test_patch_export_rejects_stale_expired_outside_and_existing(self):
        class Complete:
            def complete(self, *args, **kwargs):
                return dict(text='def f():\n    return 2\n', complete=True)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'sample.py'
            original = b'def f():\n    return 1\n'
            path.write_bytes(original)
            session = W.ProposalSession(Complete())
            request = dict(file=str(path), symbol='f', instruction='Use two')
            result = session.propose(request)
            output = root / 'fix.patch'
            output.write_bytes(b'do not overwrite')
            with self.assertRaises(FileExistsError):
                session.export_patch(result['proposal_id'], root, output)
            self.assertEqual(output.read_bytes(), b'do not overwrite')
            with self.assertRaises(FileExistsError):
                session.export_patch(result['proposal_id'], root, path)
            self.assertEqual(path.read_bytes(), original)
            sub = root / 'sub'
            sub.mkdir()
            with self.assertRaises(ValueError):
                session.export_patch(result['proposal_id'], sub, sub / 'fix.patch')
            self.assertFalse((sub / 'fix.patch').exists())
            path.write_bytes(original + b'# external edit\n')
            with self.assertRaises(ValueError):
                session.export_patch(result['proposal_id'], root, root / 'stale.patch')
            self.assertFalse((root / 'stale.patch').exists())
            path.write_bytes(original)
            for _ in range(8):
                session.propose(request)
            with self.assertRaises(ValueError):
                session.export_patch(result['proposal_id'], root, root / 'expired.patch')

    def test_patch_export_rejects_symlink_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'sample.py'
            original = b'def f():\n    return 1\n'
            path.write_bytes(original)
            output, target = root / 'link.patch', root / 'missing.patch'
            try:
                output.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest('symlinks unavailable')
            session = W.ProposalSession(None)
            session.proposals['p1'] = dict(file=str(path), symbol='f',
                source_sha256=W.hashlib.sha256(original).hexdigest(), text='def f():\n    return 2\n')
            with self.assertRaises(FileExistsError):
                session.export_patch('p1', root, output)
            self.assertFalse(target.exists())

    def test_export_command_dispatch(self):
        requests = '\n'.join(json.dumps(request) for request in (
            dict(export='p1', project_root='.', output='fix.patch'),
            dict(export='p1', project_root='.', output='fix.patch', instruction='ambiguous')))
        with patch.object(W.sys, 'argv', ['workbench', '--backend', 'splash']), \
             patch.object(W.sys, 'stdin', io.StringIO(requests)), \
             patch.object(W.sys, 'stdout', io.StringIO()) as stdout, \
             patch.object(W, 'SplashCompletion'), \
             patch.object(W.ProposalSession, 'export_patch', return_value=dict(exported=True, applied=False)) as export:
            W.main()
        export.assert_called_once_with('p1', '.', 'fix.patch')
        rows = [json.loads(line) for line in stdout.getvalue().splitlines()]
        self.assertTrue(rows[1]['exported'])
        self.assertEqual(rows[2]['error'], 'ValueError')

    def test_named_proposals_compile_without_executing(self):
        class Complete:
            def complete(self, *args, **kwargs):
                return dict(text=self.text, complete=True)

        cases = [
            ('def f():\n    return 1\n', 'def f(a, a):\n    return 2\n', False),
            ('def f():\n    return 1\n', 'def f():\n    break\n', False),
            ('def f():\n    return 1\n', 'def f():\n    nonlocal missing\n', False),
            ('async def f():\n    yield 1\n', 'async def f():\n    yield 1\n    return 2\n', False),
            ('return 0\ndef f():\n    return 1\n', 'def f():\n    return 2\n', False),
            ('raise RuntimeError("must not execute")\n@missing\ndef f():\n    return 1\n',
             '@missing\ndef f():\n    return 2\n', True),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.py'
            client = Complete()
            for original, replacement, valid in cases:
                for mode in ('replacement', 'edit', 'edits'):
                    with self.subTest(original=original, replacement=replacement, mode=mode):
                        path.write_bytes(original.encode())
                        marker = '@missing' if '@missing' in original else (
                            'async def' if 'async def' in original else 'def f')
                        selected = original[original.index(marker):]
                        edit = dict(old=selected, new=replacement)
                        client.text = replacement if mode == 'replacement' else json.dumps(
                            edit if mode == 'edit' else dict(edits=[edit]))
                        result = W.ProposalSession(client).propose(dict(
                            file=str(path), symbol='f', format=mode, instruction='Change function'))
                        self.assertEqual(result['reviewable'], valid)
                        self.assertEqual(path.read_bytes(), original.encode())
                        if not valid:
                            self.assertIsNone(result['proposal_id'])
                            self.assertIsNone(result['replacement_text'])
                            self.assertIsNone(result['diff_preview'])
                            self.assertTrue(result['rejection'])
            path.write_bytes(b'plain text\n')
            client.text = 'changed plain text\n'
            self.assertTrue(W.propose(client, dict(
                file=str(path), instruction='Change text'))['reviewable'])

    def test_explicit_helper_context_is_read_only_and_inherited(self):
        class Complete:
            text = 'def f():\n    return helper(2)\n'
            def complete(self, messages, *args, **kwargs):
                self.messages = messages
                return dict(text=self.text, complete=True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'helpers.py'
            helper = '@decorator\ndef helper(x):\n    return x * 2\n'
            other = 'def unrelated():\n    return "NOT_REQUESTED"\n'
            raw = (helper + other + 'def f():\n    return helper(1)\n').encode()
            path.write_bytes(raw)
            client = Complete()
            session = W.ProposalSession(client)
            request = dict(file=str(path), symbol='f', instruction='Use 2')
            baseline = session.propose(request)
            self.assertNotIn('READ-ONLY CONTEXT', client.messages[1]['content'])
            self.assertEqual(baseline['context_bytes'], 0)
            result = session.propose(dict(request, context_symbols=['helper']))
            self.assertTrue(result['reviewable'])
            self.assertIn(helper, client.messages[1]['content'])
            self.assertNotIn('NOT_REQUESTED', client.messages[1]['content'])
            self.assertEqual(result['context_bytes'], len(helper.encode()))
            self.assertEqual(result['context_sha256'], W.hashlib.sha256(helper.encode()).hexdigest())
            self.assertTrue(result['replacement_text'].startswith(helper + other))
            client.text = 'def f():\n    return helper(3)\n'
            revision = session.propose(dict(revise=result['proposal_id'], instruction='Use 3'))
            self.assertEqual(revision['context_symbols'], ['helper'])
            self.assertEqual(revision['context_sha256'], result['context_sha256'])
            client.text = 'def f():\n    return helper(4)\n'
            cleared = session.propose(dict(revise=revision['proposal_id'], instruction='Use 4', context_symbols=[]))
            self.assertEqual(cleared['context_symbols'], [])
            self.assertNotIn('READ-ONLY CONTEXT', client.messages[1]['content'])
            self.assertEqual(path.read_bytes(), raw)
            path.write_bytes(raw.replace(b'x * 2', b'x * 3'))
            with self.assertRaises(ValueError):
                session.propose(dict(revise=result['proposal_id'], instruction='Use 3'))

    def test_invalid_helper_context_never_calls_model(self):
        class Complete:
            def complete(self, *args, **kwargs):
                raise AssertionError('model must not be called')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'helpers.py'
            base = 'def helper():\n    return 1\ndef f():\n    return 1\n'
            path.write_bytes(base.encode())
            request = dict(file=str(path), symbol='f', instruction='Edit')
            for names in (None, 'helper', ['helper','helper'], ['f'], ['missing'], ['x.y'], [1], ['a','b','c','d','e']):
                with self.subTest(names=names), self.assertRaises(ValueError):
                    W.propose(Complete(), dict(request, context_symbols=names))
            with self.assertRaises(ValueError):
                W.propose(Complete(), dict(request, symbol=None, context_symbols=['helper']))
            for extra in ('def helper():\n    return 2\n', ''):
                source = base + extra if extra else 'def helper():\n    #' + 'é'*5000 + '\n    return 1\ndef f():\n    return 1\n'
                path.write_bytes(source.encode())
                with self.assertRaises(ValueError):
                    W.propose(Complete(), dict(request, context_symbols=['helper']))

    def test_helper_cannot_be_edited_through_context(self):
        class Complete:
            text = ''
            def complete(self, *args, **kwargs): return dict(text=self.text, complete=True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'helpers.py'
            raw = b'def helper():\n    return 99\ndef f():\n    return helper()\n'
            path.write_bytes(raw)
            client = Complete()
            request = dict(file=str(path),symbol='f',instruction='Edit',context_symbols=['helper'])
            client.text = '{"old":"return 99","new":"return 100"}'
            self.assertFalse(W.propose(client,dict(request,format='edit'))['reviewable'])
            client.text = 'def f():\n    return 1\ndef helper():\n    return 100\n'
            self.assertFalse(W.propose(client,request)['reviewable'])
            self.assertEqual(path.read_bytes(),raw)

    def test_large_module_small_selection_and_revision(self):
        class Complete:
            def complete(self, messages, *args, **kwargs):
                self.prompt = messages[-1]['content']
                return dict(text='def f():\n    return 2\n', complete=True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'large.py'
            prefix = '#' + 'x' * 40000 + '\n'
            raw = (prefix + 'def f():\n    return 1\n').encode()
            path.write_bytes(raw)
            client = Complete()
            session = W.ProposalSession(client)
            result = session.propose(dict(file=str(path), symbol='f', instruction='Return 2'))
            self.assertTrue(result['reviewable'])
            self.assertEqual(result['replacement_text'], prefix + 'def f():\n    return 2\n')
            self.assertNotIn('x' * 100, client.prompt)
            unchanged = session.propose(dict(revise=result['proposal_id'], instruction='Return 2'))
            self.assertFalse(unchanged['reviewable'])
            self.assertEqual(path.read_bytes(), raw)
            with self.assertRaises(ValueError):
                session.propose(dict(file=str(path), instruction='Edit'))
            with self.assertRaises(ValueError):
                W.propose(client, dict(file=str(path), symbol='f', instruction='Edit'), base_source='x' * 1048577)
            path.write_bytes(raw + b'#changed')
            with self.assertRaises(ValueError):
                session.propose(dict(revise=result['proposal_id'], instruction='Edit'))

    def test_large_edit_size_boundaries(self):
        class Complete:
            calls = 0
            text = 'def f():\n    return 2\n'
            def complete(self, *args, **kwargs):
                self.calls += 1
                return dict(text=self.text, complete=True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'large.py'
            client = Complete()
            request = dict(file=str(path), symbol='f', instruction='Edit')
            for raw in (b'#' + b'x' * 1048576, b'def f():\n    #' + b'x' * 33000 + b'\n    return 1\n'):
                path.write_bytes(raw)
                with self.assertRaises(ValueError): W.propose(client, request)
                self.assertEqual(client.calls, 0)
            tail = b'\ndef f():\n    return 1\n'
            path.write_bytes(b'#' + b'x' * (1048576-len(tail)-1) + tail)
            self.assertTrue(W.propose(client, request)['reviewable'])
            client.text = 'def f():\n    #' + 'x' * 33000 + '\n    return 2\n'
            self.assertFalse(W.propose(client, request)['reviewable'])

    def test_edit_unicode_errors_are_value_errors(self):
        cases = [('\ud800abc', '{"old":"a","new":"x"}'), ('abc', '\ud800')]
        for item in ({'old': 'a', 'new': '\ud800'}, {'old': '\udfff', 'new': 'x'}):
            cases.append(('abc', json.dumps(item)))
        for selected, envelope in cases:
            with self.subTest(selected=repr(selected), envelope=repr(envelope)):
                with self.assertRaises(ValueError) as caught:
                    W.reconstruct_edit(selected, envelope)
                self.assertNotIsInstance(caught.exception, UnicodeEncodeError)
        self.assertEqual(W.reconstruct_edit('a😀c', json.dumps({'old': '😀', 'new': '🦉'})), 'a🦉c')
        with self.assertRaises(ValueError) as caught:
            W.reconstruct_edit('abc', json.dumps({'edits': [{'old': 'a', 'new': '\ud800'}]}), multiple=True)
        self.assertNotIsInstance(caught.exception, UnicodeEncodeError)

    def test_reasoning_cli_is_splash_only(self):
        with patch.object(W.sys, 'argv', ['workbench', '--backend', 'splash', '--reasoning-effort', 'low']), \
             patch.object(W.sys, 'stdin', io.StringIO('')), \
             patch.object(W.sys, 'stdout', io.StringIO()), \
             patch.object(W, 'SplashCompletion', return_value=object()) as completion:
            W.main()
        self.assertEqual(completion.call_args.kwargs['reasoning_effort'], 'low')
        with patch.object(W.sys, 'argv', ['workbench', '--reasoning-effort', 'low']), \
             patch.object(W.sys, 'stderr', io.StringIO()), \
             patch.object(W, 'MLXBackend') as backend:
            with self.assertRaises(SystemExit) as error:
                W.main()
            self.assertEqual(error.exception.code, 2)
            backend.assert_not_called()

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
