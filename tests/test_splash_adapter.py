"""Local HTTP fixture tests, NOT qualification against a running Splash engine."""
import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    'workbench', Path(__file__).resolve().parents[1] / 'experiments/workbench.py')
W = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(W)


class SplashAdapterTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.status = 200
        self.reply = {'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant',
                      'content': 'def f():\n    return 2\n'}}], 'usage': {'completion_tokens': 10}}
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                owner.requests.append((self.path, dict(self.headers),
                    json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                self.send_response(owner.status)
                if owner.status == 307:
                    self.send_header('Location', 'http://example.invalid/receive')
                self.end_headers()
                self.wfile.write(json.dumps(owner.reply).encode())
            def log_message(self, *args):
                pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = W.SplashCompletion('http://127.0.0.1:' + str(self.server.server_port), 'fixture-model')

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_proposal_revision_and_explicit_server_owned_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.py'
            original = b'def f():\n    return 1\n'
            path.write_bytes(original)
            session = W.ProposalSession(self.client)
            first = session.propose({'file': str(path), 'symbol': 'f', 'instruction': 'Return 2'})
            self.reply['choices'][0]['message']['content'] = 'def f():\n    return 3\n'
            second = session.propose({'revise': first['proposal_id'], 'instruction': 'Return 3'})
            self.assertTrue(second['reviewable'])
            self.assertIn('return 2', self.requests[1][2]['messages'][1]['content'])
            self.assertIn('-    return 1', second['diff_preview'])
            self.assertEqual(path.read_bytes(), original)
            self.assertIsNone(second['model_calls'])
            self.assertIsNone(second['draft_tokens_verified'])
            self.assertEqual(second['draft_origin'], 'server_managed')
            self.assertEqual(self.requests[0][0], '/v1/chat/completions')
            self.assertEqual(self.requests[0][2]['reasoning_effort'], 'none')
            self.assertEqual(self.requests[0][2]['model'], 'fixture-model')

    def test_length_limit_is_not_complete(self):
        self.reply['choices'][0]['finish_reason'] = 'length'
        self.assertFalse(self.client.complete([])['complete'])

    def test_input_token_accounting_is_explicit_and_strict(self):
        for tokens in (None, 0, 123):
            with self.subTest(tokens=tokens):
                self.reply['usage']['prompt_tokens'] = tokens
                result = self.client.complete([])
                self.assertEqual(result['input_tokens'], tokens)
                self.assertEqual(result['output_tokens'], 10)
        del self.reply['usage']['prompt_tokens']
        self.assertIsNone(self.client.complete([])['input_tokens'])
        for tokens in (True, False, -1, 1.5, '12', [], {}):
            with self.subTest(tokens=tokens):
                self.reply['usage']['prompt_tokens'] = tokens
                with self.assertRaises(ValueError):
                    self.client.complete([])

    def test_invalid_or_tool_responses_rejected(self):
        for reply in ({}, {'choices': []}, {'choices': [{'finish_reason': 'stop', 'message': {
            'content': 'text', 'tool_calls': [{'id': 'x'}]}}]},
            {'choices': [{'finish_reason': 'tool_calls', 'message': {'content': 'text'}}]},
            {'choices': [{'finish_reason': 'stop', 'message': {'content': None}}]}):
            with self.subTest(reply=reply):
                self.reply = reply
                with self.assertRaises(ValueError):
                    self.client.complete([])

    def test_redirect_not_followed(self):
        self.status = 307
        with self.assertRaisesRegex(RuntimeError, '307'):
            self.client.complete([])
        self.assertEqual(len(self.requests), 1)

    def test_api_key_and_proxy_isolation(self):
        with patch.dict('os.environ', {'SPLASH_API_KEY': 'fixture-key',
                        'HTTP_PROXY': 'http://127.0.0.1:1', 'http_proxy': 'http://127.0.0.1:1',
                        'NO_PROXY': '', 'no_proxy': ''}):
            self.client.complete([])
        self.assertEqual(self.requests[0][1]['Authorization'], 'Bearer fixture-key')

    def test_invalid_key_not_echoed_or_sent(self):
        with patch.dict('os.environ', {'SPLASH_API_KEY': 'private-fixture\nvalue'}):
            with self.assertRaisesRegex(ValueError, '^invalid SPLASH_API_KEY header characters$'):
                self.client.complete([])
        self.assertEqual(self.requests, [])

    def test_only_loopback_urls_allowed(self):
        for url in ('https://example.com', 'http://example.com', 'http://localhost:8000',
                    'http://127.0.0.1@evil.invalid', 'http://127.0.0.1/path',
                    'http://127.0.0.1?redirect=x', 'http://127.0.0.1/#x'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                W.SplashCompletion(url)

    def test_http_error_no_body_or_retry(self):
        self.status = 500
        self.reply = {'private': 'not for exception display'}
        with self.assertRaisesRegex(RuntimeError, '^Splash HTTP 500; no retry or redirect performed$'):
            self.client.complete([])
        self.assertEqual(len(self.requests), 1)


if __name__ == '__main__':
    unittest.main()
