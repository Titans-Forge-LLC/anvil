import json
import io
import os
import tempfile
from contextlib import redirect_stdout
import subprocess
import unittest
from pathlib import Path

from anvil_alpha import AVP1Codec, CodecError, ContextMismatchError, canonical_json
from anvil_alpha.cli import _write


ROOT = Path(__file__).resolve().parents[1]


class AVP1CodecTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
