import json
import io
import os
import tempfile
from contextlib import redirect_stdout
import subprocess
import unittest
from unittest.mock import patch
from pathlib import Path

from anvil_alpha import AVP1Codec, CodecError, ContextMismatchError, canonical_json
from anvil_alpha.cli import _write
from anvil_alpha import cli


ROOT = Path(__file__).resolve().parents[1]


class AVP1CodecTests(unittest.TestCase):
    def test_cli_pipeline_and_file_operands(self):
        source = {'authority': {'allow': ['read']}, 'text': 'café', 'value': 3}
        payload = json.dumps(source)

        def run(args, stdin=''):
            with patch.object(cli.sys, 'stdin', io.StringIO(stdin)), redirect_stdout(io.StringIO()) as out:
                self.assertEqual(cli.main(args), 0)
                return out.getvalue()

        wire = run(['encode', '-', '-'], payload)
        self.assertEqual(json.loads(run(['decode', '-', '-'], wire)), source)
        self.assertTrue(json.loads(run(['benchmark', '-'], payload))['semantic_exact'])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src, packed, dst = root / 'source.json', root / 'wire.avp1', root / 'decoded.json'
            src.write_text(payload, encoding='utf-8')
            run(['encode', str(src), str(packed)])
            run(['decode', str(packed), str(dst)])
            self.assertEqual(json.loads(dst.read_text(encoding='utf-8')), source)
            self.assertTrue(json.loads(run(['verify', '-', str(packed)], payload))['semantic_exact'])
            self.assertTrue(json.loads(run(['verify', str(src), '-'], wire))['authority_exact'])
            self.assertTrue(json.loads(run(['verify', str(src), str(packed)]))['semantic_exact'])

    def test_cli_double_stdin_rejected_before_reading(self):
        class NoRead:
            def read(self, *args):
                raise AssertionError('must reject before reading')
        with patch.object(cli.sys, 'stdin', NoRead()), patch.object(cli.sys, 'stderr', io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                cli.main(['verify', '-', '-'])
        self.assertEqual(error.exception.code, 2)

    def test_cli_malformed_streams_rejected(self):
        for command, value in [('encode', 'not JSON'), ('decode', 'not a wire')]:
            with self.subTest(command=command), patch.object(cli.sys, 'stdin', io.StringIO(value)):
                with self.assertRaises(ValueError):
                    cli.main([command, '-'])

    def test_cli_write_adds_only_missing_newline(self):
        for text in ('', 'hello', 'hello\n', 'hello\n\n', 'café\n', 'x\r\n'):
            expected = text if text.endswith('\n') else text + '\n'
            with self.subTest(text=text), tempfile.TemporaryDirectory() as directory:
                output = io.StringIO()
                with redirect_stdout(output):
                    _write(None, text)
                self.assertEqual(output.getvalue(), expected)
                path = Path(directory) / 'out.txt'
                _write(path, text)
                # Retain Python's existing platform-native text-file translation.
                self.assertEqual(path.read_bytes(), expected.replace('\n', os.linesep).encode('utf-8'))

    def setUp(self):
        self.codec = AVP1Codec()
        self.sample = json.loads((ROOT / "examples/governed_mission.json").read_text())

    def test_exact_round_trip(self):
        wire = self.codec.encode(self.sample)
        self.assertEqual(canonical_json(self.sample), canonical_json(self.codec.decode(wire)))

    def test_non_string_keys_raise_codec_error_before_sorting(self):
        for value in ({1: 'x', 'a': 'y'}, {'a': 'y', 1: 'x'},
                      {'nested': [{1: 'x', 'a': 'y'}]}, {1: 'x'}):
            with self.subTest(value=value):
                with self.assertRaisesRegex(CodecError, '^JSON object keys must be strings$'):
                    self.codec.encode(value)

    def test_authority_round_trip(self):
        decoded = self.codec.decode(self.codec.encode(self.sample))
        self.assertEqual(self.sample["authority"], decoded["authority"])

    def test_wrong_profile_fails_closed(self):
        wire = self.codec.encode(self.sample)
        with self.assertRaises(ContextMismatchError):
            AVP1Codec("wrong-profile").decode(wire)

    def test_corruption_rejected(self):
        wire = self.codec.encode(self.sample)
        with self.assertRaises(CodecError):
            self.codec.decode(wire[:-1])

    def test_reserved_prefixes_escape(self):
        source = {"@0": "#0", "ordinary": "##literal", "version": "0.1"}
        decoded = self.codec.decode(self.codec.encode(source))
        self.assertEqual(source, decoded)

    def test_encoding_is_deterministic(self):
        reversed_source = dict(reversed(list(self.sample.items())))
        self.assertEqual(self.codec.encode(self.sample), self.codec.encode(reversed_source))

    def test_shipped_fixture_cross_runtime(self):
        script = ("import {encode,decode} from './site/codec.mjs';"
                  "import {readFileSync} from 'node:fs';"
                  "const v=JSON.parse(readFileSync('examples/governed_mission.json','utf8'));"
                  "const w=encode(v);decode(w);process.stdout.write(w);")
        wire = subprocess.check_output(['node','--input-type=module','-e',script],cwd=ROOT,text=True)
        self.assertEqual(wire,self.codec.encode(self.sample))
        self.assertEqual(self.codec.decode(wire),self.sample)

    def test_key_order_and_data_properties_cross_runtime(self):
        cases = [
            {'10': 1, '2': 2},
            {'4294967294': 1, '9': 2, '01': 3, '0': 4},
            {'\U00010000': 1, '\ue000': 2},
            {'a\U00010000': 1, 'a\ue000': 2, 'a': 3, 'aa': 4},
            {'é': 'composed', 'e\u0301': 'decomposed', '': 'empty'},
            {'nested': [{'10': 1, '2': 2}, {'\U0001f600': 1, '\uffff': 2}]},
            {'__proto__': {'polluted': True}, 'constructor': 'data'},
            {'@0': '#0', 'version': '0.1', '10': {'2': '@a'}},
        ]
        script = """
import {canonicalJson, encode, decode} from './site/codec.mjs';
import {readFileSync} from 'node:fs';
const cases = JSON.parse(readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(cases.map(row => ({
  canonical: canonicalJson(row.value), wire: encode(row.value),
  decoded: decode(row.wire)
}))));
"""
        records = [{'value': v, 'wire': self.codec.encode(v)} for v in cases]
        result = subprocess.run(['node', '--input-type=module', '-e', script],
                                cwd=ROOT, input=json.dumps(records), encoding='utf-8',
                                capture_output=True, check=True, timeout=15)
        decoded_results = json.loads(result.stdout)
        self.assertEqual(len(decoded_results), len(cases))
        for value, actual in zip(cases, decoded_results):
            with self.subTest(value=value):
                self.assertEqual(actual['canonical'], canonical_json(value))
                self.assertEqual(actual['wire'], self.codec.encode(value))
                self.assertEqual(actual['decoded'], value)
                self.assertEqual(self.codec.decode(actual['wire']), value)


if __name__ == "__main__":
    unittest.main()
