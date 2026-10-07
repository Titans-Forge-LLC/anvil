"""Opt-in HTTP response replay tests: mocked I/O, no live server or model."""
import copy
import hashlib
import importlib.util
import io
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error


SPEC = importlib.util.spec_from_file_location(
    'http_reuse_workbench', Path(__file__).resolve().parents[1] / 'experiments/workbench.py')
W = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(W)


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class HTTPReuseTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(W.os.environ,
                                      {'SPLASH_API_KEY': '', 'TENSORFOLD_API_KEY': ''})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.reply = {
            'choices': [{'finish_reason': 'stop', 'message': {
                'role': 'assistant', 'content': 'def f():\n    return 2\n'}}],
            'usage': {'prompt_tokens': 23, 'completion_tokens': 11},
        }
        self.requests = []
        self.error = None
        self.raw = None
        self.opener = Mock(spec=['open'])
        self.opener.open.side_effect = self.open_response
        self.messages = [{'role': 'user', 'content': 'fixture source and request'}]

    def open_response(self, request, **options):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        raw = self.raw if self.raw is not None else json.dumps(self.reply).encode('utf-8')
        return Response(raw)

    def client(self, backend='splash', **options):
        adapter = W.SplashCompletion if backend == 'splash' else W.TensorFoldCompletion
        client = adapter('http://127.0.0.1:18420', 'fixture-model', **options)
        client.opener = self.opener
        return client

    def assert_hit(self, result, delivered=11):
        self.assertTrue(result['exact_hit'])
        self.assertTrue(result['complete'])
        self.assertEqual(result['http_requests'], 0)
        self.assertEqual(result['model_calls'], 0)
        self.assertEqual(result['input_tokens'], 0)
        self.assertEqual(result['output_tokens'], 0)
        self.assertEqual(result['delivered_output_tokens'], delivered)
        self.assertEqual(result['draft_origin'], 'retained_response')
        for field in ('prefix_tokens_reused', 'draft_tokens_verified', 'draft_tokens_scored'):
            self.assertIsNone(result[field])
        metrics = result.get('server_metrics')
        if metrics is not None:
            self.assertIsInstance(metrics, dict)
            self.assertTrue(all(value is None for value in metrics.values()))
        self.assertIsInstance(result['retained_response'], dict)

    def test_default_off_and_explicit_false_always_issue_http(self):
        for backend in ('splash', 'tensorfold'):
            for options in ({}, {'reuse_responses': False}):
                with self.subTest(backend=backend, options=options):
                    client = self.client(backend, **options)
                    before = len(self.requests)
                    first = client.complete(self.messages)
                    second = client.complete(self.messages)
                    self.assertEqual(len(self.requests), before + 2)
                    self.assertFalse(first['exact_hit'])
                    self.assertFalse(second['exact_hit'])
                    self.assertEqual(second['delivered_output_tokens'], 11)
                    self.assertEqual(client.clear_responses(), 0)

    def test_opt_in_hit_reports_only_lookup_work_and_historical_metadata(self):
        for backend in ('splash', 'tensorfold'):
            with self.subTest(backend=backend):
                client = self.client(backend, reuse_responses=True)
                if backend == 'tensorfold':
                    self.reply.update(tensorfold={'seconds': 4.5, 'prefill_seconds': 0.4},
                                      speculative={'rounds': 2, 'drafted': 20, 'accepted': 10})
                    self.reply['usage']['prompt_tokens_details'] = {'cached_tokens': 7}
                before = len(self.requests)
                with patch.object(W.time, 'perf_counter', side_effect=itertools.count(0, 10)):
                    first = client.complete(self.messages)
                with patch.object(W.time, 'perf_counter', side_effect=itertools.count(0, 0.01)):
                    replay = client.complete(copy.deepcopy(self.messages))
                self.assertEqual(len(self.requests), before + 1)
                self.assertFalse(first['exact_hit'])
                self.assertEqual(first['http_requests'], 1)
                self.assertIsNone(first['model_calls'])
                self.assertEqual(first['input_tokens'], 23)
                self.assertEqual(first['output_tokens'], 11)
                self.assertEqual(first['delivered_output_tokens'], 11)
                self.assert_hit(replay)
                self.assertEqual(replay['text'], first['text'])
                self.assertGreaterEqual(replay['completion_seconds'], 0)
                self.assertLess(replay['completion_seconds'], first['completion_seconds'])
                history = replay['retained_response']
                for field in ('backend', 'http_requests', 'model_calls', 'input_tokens',
                              'output_tokens', 'prefix_tokens_reused'):
                    self.assertEqual(history[field], first[field])
                # Historical timing ends after acquisition/validation; the
                # delivered miss also charges retention bookkeeping.
                self.assertGreater(history['completion_seconds'], replay['completion_seconds'])
                self.assertLessEqual(history['completion_seconds'], first['completion_seconds'])
                if backend == 'tensorfold':
                    self.assertEqual(first['prefix_tokens_reused'], 7)
                    self.assertEqual(first['server_metrics']['accepted_tokens'], 10)
                    self.assertEqual(history['server_metrics'], first['server_metrics'])
                forbidden = {'text', 'messages', 'payload', 'source', 'replacement_text',
                             'authorization', 'credential', 'api_key', 'approved', 'executed_check'}
                self.assertFalse(forbidden.intersection(history))
                self.assertNotIn(first['text'], json.dumps(history))

    def test_unknown_output_token_count_remains_unknown_when_delivered(self):
        self.reply.pop('usage')
        client = self.client(reuse_responses=True)
        first = client.complete(self.messages)
        self.assertIsNone(first['delivered_output_tokens'])
        self.assert_hit(client.complete(self.messages), delivered=None)
        self.assertEqual(len(self.requests), 1)

    def test_key_binds_full_payload_endpoint_and_backend_label(self):
        class DistinctSplash(W.SplashCompletion):
            pass

        client = self.client(reuse_responses=True)
        client.complete(self.messages)
        changes = (
            ({'messages': [{'role': 'user', 'content': 'different source'}]}, None),
            ({'max_tokens': 513}, None),
            ({'reasoning_effort': 'low'}, None),
            ({}, ('model', 'different-model')),
            ({}, ('endpoint', 'http://127.0.0.1:18421/v1/chat/completions')),
            ({}, ('backend_name', 'fixture_splash_http')),
            ({}, ('__class__', DistinctSplash)),
        )
        for options, attribute in changes:
            with self.subTest(options=options, attribute=attribute):
                old = getattr(client, attribute[0]) if attribute else None
                if attribute:
                    setattr(client, *attribute)
                kwargs = dict(options)
                messages = kwargs.pop('messages', self.messages)
                before = len(self.requests)
                self.assertFalse(client.complete(messages, **kwargs)['exact_hit'])
                self.assertEqual(len(self.requests), before + 1)
                self.assert_hit(client.complete(messages, **kwargs))
                if attribute:
                    setattr(client, attribute[0], old)
        self.assert_hit(client.complete(self.messages))

    def test_tensorfold_key_binds_sampling_thinking_and_draft(self):
        client = self.client('tensorfold', reuse_responses=True)
        client.complete(self.messages)
        for attribute, value in (('sampling', {'temperature': 0.7, 'top_p': 0.9,
                                               'top_k': 25, 'seed': 12}),
                                 ('thinking', True), ('draft', False)):
            with self.subTest(attribute=attribute):
                old = getattr(client, attribute)
                setattr(client, attribute, value)
                before = len(self.requests)
                self.assertFalse(client.complete(self.messages)['exact_hit'])
                self.assertEqual(len(self.requests), before + 1)
                self.assert_hit(client.complete(self.messages))
                setattr(client, attribute, old)

    def test_current_credential_and_backend_specific_env_isolate_replay(self):
        for backend, own, other in (
                ('splash', 'SPLASH_API_KEY', 'TENSORFOLD_API_KEY'),
                ('tensorfold', 'TENSORFOLD_API_KEY', 'SPLASH_API_KEY')):
            with self.subTest(backend=backend):
                client = self.client(backend, reuse_responses=True)
                before = len(self.requests)
                with patch.dict(W.os.environ, {own: 'fixture-alpha', other: 'other-alpha'}):
                    client.complete(self.messages)
                    self.assertEqual(self.requests[-1].get_header('Authorization'), 'Bearer fixture-alpha')
                with patch.dict(W.os.environ, {own: 'fixture-beta'}):
                    self.assertFalse(client.complete(self.messages)['exact_hit'])
                with patch.dict(W.os.environ, {own: 'fixture-alpha', other: 'other-beta'}):
                    replay = client.complete(self.messages)
                    self.assert_hit(replay)
                    self.assertNotIn('fixture-alpha', json.dumps(replay))
                    self.assertNotIn('fixture-beta', json.dumps(replay))
                with patch.dict(W.os.environ, {own: ''}):
                    self.assertFalse(client.complete(self.messages)['exact_hit'])
                    self.assertIsNone(self.requests[-1].get_header('Authorization'))
                self.assertEqual(len(self.requests), before + 3)

    def test_header_and_request_validation_precede_any_replay(self):
        for backend, own in (('splash', 'SPLASH_API_KEY'),
                             ('tensorfold', 'TENSORFOLD_API_KEY')):
            with self.subTest(backend=backend):
                client = self.client(backend, reuse_responses=True)
                client.complete(self.messages)
                before = len(self.requests)
                for key in ('private-fixture\nvalue', 'private-fixture\rvalue',
                            'private-fixture\x00value', 'private-fixture\x7fvalue', 'private-fixture-é'):
                    # A real process environment cannot contain NUL; replacing
                    # the mapping lets us exercise the adapter's guard itself.
                    with self.subTest(key=repr(key)), patch.object(W.os, 'environ', {own: key}):
                        with self.assertRaises(ValueError) as rejected:
                            client.complete(self.messages)
                        self.assertNotIn('private-fixture', str(rejected.exception))
                for budget in (True, 0, 4097, '512'):
                    with self.subTest(budget=budget), self.assertRaises(ValueError):
                        client.complete(self.messages, max_tokens=budget)
                with self.assertRaises(ValueError):
                    client.complete(self.messages, reasoning_effort='invalid')
                with self.assertRaises((TypeError, ValueError)):
                    client.complete([{'role': 'user', 'content': object()}])
                with self.assertRaisesRegex(ValueError, 'request exceeds'):
                    client.complete([{'role': 'user', 'content': 'x' * 262144}])
                self.assertEqual(len(self.requests), before)
                self.assert_hit(client.complete(self.messages))

    def test_partial_invalid_and_tool_responses_are_never_cached(self):
        original = copy.deepcopy(self.reply)
        cases = [
            ('partial', {'choices': [{'finish_reason': 'length', 'message': {'content': 'partial'}}]}),
            ('tool', {'choices': [{'finish_reason': 'stop', 'message': {'content': 'text',
                                                                        'tool_calls': [{'id': 'x'}]}}]}),
            ('function', {'choices': [{'finish_reason': 'stop', 'message': {'content': 'text',
                                                                            'function_call': {'name': 'f'}}}]}),
            ('refusal', {'choices': [{'finish_reason': 'stop', 'message': {'content': 'text',
                                                                           'refusal': 'no'}}]}),
            ('bad_choice', {'choices': []}),
            ('blank_text', {'choices': [{'finish_reason': 'stop', 'message': {'content': '  '}}]}),
            ('bad_tokens', dict(original, usage={'completion_tokens': True})),
            ('bad_prompt_tokens', dict(original, usage={'prompt_tokens': -1})),
        ]
        for name, reply in cases:
            with self.subTest(case=name):
                client = self.client(reuse_responses=True)
                self.reply = reply
                before = len(self.requests)
                for attempt in range(2):
                    if name == 'partial':
                        result = client.complete(self.messages)
                        self.assertFalse(result['complete'])
                        self.assertFalse(result['exact_hit'])
                    else:
                        with self.assertRaises(ValueError):
                            client.complete(self.messages)
                self.assertEqual(len(self.requests), before + 2)
                self.assertEqual(client.clear_responses(), 0)
                self.reply = copy.deepcopy(original)
                self.assertFalse(client.complete(self.messages)['exact_hit'])
                self.assert_hit(client.complete(self.messages))

    def test_tensorfold_metadata_is_validated_before_retention(self):
        original = copy.deepcopy(self.reply)
        cases = ({'tensorfold': {'seconds': -1}}, {'tensorfold': {'seconds': float('nan')}},
                 {'tensorfold': ['invalid']}, {'speculative': {'accepted': True}},
                 {'speculative': {'rounds': 1.5}},
                 {'usage': {'prompt_tokens_details': {'cached_tokens': -1}}})
        for changes in cases:
            with self.subTest(changes=changes):
                client = self.client('tensorfold', reuse_responses=True)
                self.reply = dict(copy.deepcopy(original), **changes)
                before = len(self.requests)
                for attempt in range(2):
                    with self.assertRaisesRegex(ValueError, 'invalid TensorFold metric'):
                        client.complete(self.messages)
                self.assertEqual(len(self.requests), before + 2)
                self.assertEqual(client.clear_responses(), 0)
                self.reply = copy.deepcopy(original)
                self.assertFalse(client.complete(self.messages)['exact_hit'])
                self.assert_hit(client.complete(self.messages))

    def test_connection_http_and_decode_errors_are_never_cached_or_retried(self):
        client = self.client(reuse_responses=True)
        for error in (urllib.error.URLError('private failure'), TimeoutError('private failure'),
                      OSError('private failure')):
            with self.subTest(error=type(error).__name__):
                self.error = error
                before = len(self.requests)
                for attempt in range(2):
                    with self.assertRaisesRegex(RuntimeError, 'no automatic retry'):
                        client.complete(self.messages)
                self.assertEqual(len(self.requests), before + 2)
                self.assertEqual(client.clear_responses(), 0)
        for attempt in range(2):
            self.error = urllib.error.HTTPError('http://127.0.0.1:18420', 500, 'private failure',
                                                 {}, io.BytesIO(b'private response body'))
            with self.assertRaisesRegex(RuntimeError, 'HTTP 500; no retry or redirect'):
                client.complete(self.messages)
        self.error = None
        for raw in (b'{broken', b'{}', b'x' * 1048577):
            with self.subTest(raw_length=len(raw)):
                self.raw = raw
                before = len(self.requests)
                for attempt in range(2):
                    with self.assertRaises(ValueError):
                        client.complete(self.messages)
                self.assertEqual(len(self.requests), before + 2)
                self.assertEqual(client.clear_responses(), 0)
        self.raw = None
        self.assertFalse(client.complete(self.messages)['exact_hit'])
        self.assert_hit(client.complete(self.messages))

    def test_response_lru_promotes_hits_and_evicts_at_32_entries(self):
        client = self.client(reuse_responses=True)
        messages = [[{'role': 'user', 'content': f'fixture {index}'}] for index in range(33)]
        for item in messages[:32]:
            self.assertFalse(client.complete(item)['exact_hit'])
        self.assert_hit(client.complete(messages[0]))
        self.assertFalse(client.complete(messages[32])['exact_hit'])
        self.assert_hit(client.complete(messages[0]))
        self.assert_hit(client.complete(messages[2]))
        self.assertFalse(client.complete(messages[1])['exact_hit'])
        self.assertEqual(len(self.requests), 34)
        self.assertEqual(client.clear_responses(), 32)
        self.assertEqual(client.clear_responses(), 0)
        self.assertFalse(client.complete(messages[0])['exact_hit'])

    def test_response_byte_bound_includes_serialized_key_and_result(self):
        # Five outputs fit under 4 MiB alone. Including five 200 KiB request
        # keys exceeds the limit; exactly four entries fit with ample margin.
        client = self.client(reuse_responses=True)
        self.reply['choices'][0]['message']['content'] = 'r' * 750000
        messages = [[{'role': 'user', 'content': str(index) + 'q' * 200000}]
                    for index in range(5)]
        for item in messages:
            self.assertFalse(client.complete(item)['exact_hit'])
        self.assert_hit(client.complete(messages[-1]))
        self.assertEqual(client.clear_responses(), 4)
        self.assertEqual(client.clear_responses(), 0)

    def test_returned_results_are_independent_deep_copies(self):
        client = self.client('tensorfold', reuse_responses=True, temperature=0.7)
        self.reply.update(tensorfold={'seconds': 2.5}, speculative={'accepted': 4})
        self.reply['usage']['prompt_tokens_details'] = {'cached_tokens': 6}
        first = client.complete(self.messages)
        first['text'] = 'caller-mutated fresh text'
        first['sampling_requested']['temperature'] = 99
        first['server_metrics']['seconds'] = 99
        replay = client.complete(self.messages)
        self.assert_hit(replay)
        self.assertEqual(replay['text'], 'def f():\n    return 2\n')
        self.assertEqual(replay['sampling_requested']['temperature'], 0.7)
        self.assertEqual(replay['retained_response']['server_metrics']['seconds'], 2.5)
        replay['text'] = 'caller-mutated retained text'
        replay['sampling_requested']['temperature'] = 100
        replay['retained_response']['server_metrics']['seconds'] = 100
        replay['retained_response']['output_tokens'] = 100
        second = client.complete(self.messages)
        self.assert_hit(second)
        self.assertEqual(second['text'], 'def f():\n    return 2\n')
        self.assertEqual(second['sampling_requested']['temperature'], 0.7)
        self.assertEqual(second['retained_response']['server_metrics']['seconds'], 2.5)
        self.assertEqual(second['retained_response']['output_tokens'], 11)
        self.assertEqual(len(self.requests), 1)

    def test_replayed_completion_creates_fresh_proposal_without_evidence_or_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.py'
            original = b'def f():\n    return 1\n'
            path.write_bytes(original)
            client = self.client(reuse_responses=True)
            runner = Mock(spec=['run', 'fresh_inputs'])
            runner.run.return_value = {'tests': 'executed_zero_exit', 'approved': False,
                                       'applied': False, 'candidate_sha256': 'fixture-check-hash'}
            session = W.ProposalSession(client, runner)
            request = {'file': str(path), 'symbol': 'f', 'instruction': 'Return 2'}
            first = session.propose(request)
            session.run_checks(first['proposal_id'])
            second = session.propose(request)
            self.assert_hit(second)
            self.assertTrue(second['reviewable'])
            self.assertNotEqual(first['proposal_id'], second['proposal_id'])
            self.assertIsNone(second['parent_proposal_id'])
            self.assertFalse(second['applied'])
            self.assertFalse(second.get('approved', False))
            self.assertNotIn('executed_check', session.proposals[second['proposal_id']])
            self.assertEqual(session.check_status(second['proposal_id']),
                             {'tests': 'not_run', 'approved': False})
            runner.run.assert_called_once()
            runner.fresh_inputs.assert_not_called()
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(len(self.requests), 1)

    def test_cache_hit_rebinds_current_full_source_and_preserves_other_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.py'
            original = b'STATE = 1\n\ndef f():\n    return 1\n'
            changed = original.replace(b'STATE = 1', b'STATE = 2')
            path.write_bytes(original)
            session = W.ProposalSession(self.client(reuse_responses=True))
            request = {'file': str(path), 'symbol': 'f', 'instruction': 'Return 2'}
            first = session.propose(request)
            path.write_bytes(changed)
            second = session.propose(request)
            self.assert_hit(second)
            self.assertTrue(second['reviewable'])
            self.assertNotEqual(second['source_sha256'], first['source_sha256'])
            self.assertEqual(second['source_sha256'], hashlib.sha256(changed).hexdigest())
            self.assertTrue(second['replacement_text'].startswith('STATE = 2\n'))
            self.assertEqual(path.read_bytes(), changed)
            self.assertEqual(len(self.requests), 1)
            with self.assertRaisesRegex(ValueError, 'source changed'):
                session.propose({'revise': first['proposal_id'], 'instruction': 'Return 2'})
            self.assertEqual(len(self.requests), 1)

    def test_source_change_during_cache_lookup_invalidates_proposal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.py'
            original = b'def f():\n    return 1\n'
            changed = original + b'# external edit\n'
            path.write_bytes(original)
            client = self.client(reuse_responses=True)
            session = W.ProposalSession(client)
            request = {'file': str(path), 'symbol': 'f', 'instruction': 'Return 2'}
            session.propose(request)
            complete = client.complete

            def change_after_lookup(*args, **options):
                result = complete(*args, **options)
                path.write_bytes(changed)
                return result

            with patch.object(client, 'complete', side_effect=change_after_lookup):
                result = session.propose(request)
            self.assert_hit(result)
            self.assertFalse(result['reviewable'])
            self.assertTrue(result['source_changed'])
            self.assertIsNone(result['proposal_id'])
            self.assertIsNone(result['replacement_text'])
            self.assertIsNone(result['diff_preview'])
            self.assertFalse(result['applied'])
            self.assertEqual(path.read_bytes(), changed)
            self.assertEqual(len(self.requests), 1)


class HTTPReuseCLITests(unittest.TestCase):
    def test_cli_passes_default_off_and_opt_in_to_only_http_adapters(self):
        for backend, constructor in (('splash', 'SplashCompletion'),
                                     ('tensorfold', 'TensorFoldCompletion')):
            for enabled in (False, True):
                args = ['workbench', '--backend', backend]
                if enabled:
                    args.append('--reuse-http-responses')
                with self.subTest(backend=backend, enabled=enabled), \
                     patch.object(W, constructor) as adapter, \
                     patch.object(W.sys, 'argv', args), \
                     patch.object(W.sys, 'stdin', io.StringIO()), \
                     patch.object(W.sys, 'stdout', io.StringIO()) as output:
                    W.main()
                    self.assertEqual(adapter.call_args.kwargs.get('reuse_responses', False), enabled)
                    self.assertTrue(json.loads(output.getvalue())['ready'])
                    adapter.return_value.complete.assert_not_called()
                    adapter.return_value.check_server.assert_not_called()

    def test_cli_rejects_reuse_for_mlx_and_offline_before_backend_creation(self):
        for backend in ('mlx', 'offline'):
            with self.subTest(backend=backend), \
                 patch.object(W.sys, 'argv', ['workbench', '--backend', backend,
                                               '--model', 'fixture-model', '--reuse-http-responses']), \
                 patch.object(W.sys, 'stdin', io.StringIO()), \
                 patch.object(W.sys, 'stderr', io.StringIO()) as error, \
                 patch.object(W, 'MLXBackend') as mlx, \
                 patch.object(W, 'OfflineCompletion') as offline:
                with self.assertRaises(SystemExit) as rejected:
                    W.main()
                self.assertEqual(rejected.exception.code, 2)
                self.assertIn('--reuse-http-responses', error.getvalue())
                mlx.assert_not_called()
                offline.assert_not_called()


if __name__ == '__main__':
    unittest.main()
