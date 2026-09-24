"""The CLI caps each UTF-8 input operand before decoding or writing output."""

import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from anvil_alpha import cli


LIMIT = 1_048_576


class CLILimitTests(unittest.TestCase):
    def test_json_file_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_bytes(b"{}" + b" " * (LIMIT - 2))
            self.assertEqual(cli._load_json(path), {})
            path.write_bytes(b"{}" + b" " * (LIMIT - 1))
            with self.assertRaises(ValueError):
                cli._load_json(path)

    def test_wire_file_counts_utf8_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wire.avp1"
            path.write_bytes("é".encode() * (LIMIT // 2))
            self.assertEqual(len(cli._read_text(path).encode()), LIMIT)
            path.write_bytes("é".encode() * (LIMIT // 2 + 1))
            with self.assertRaises(ValueError):
                cli._read_text(path)

    def test_text_only_stdin_counts_bytes_and_bounds_read(self):
        class TextOnly:
            def __init__(self, text):
                self.text = text
                self.calls = []

            def read(self, count=-1):
                self.calls.append(count)
                if count < 0:
                    raise AssertionError("unbounded read")
                return self.text[:count]

        small = TextOnly("{}")
        with patch.object(cli.sys, "stdin", small):
            self.assertEqual(cli._load_json(Path("-")), {})
        self.assertEqual(small.calls, [LIMIT + 1])
        large = TextOnly('"' + "é" * (LIMIT // 2) + '"')
        with patch.object(cli.sys, "stdin", large):
            with self.assertRaises(ValueError):
                cli._load_json(Path("-"))
        self.assertEqual(large.calls, [LIMIT + 1])

    def test_binary_stdin_bounds_read(self):
        class BinaryStdin:
            def __init__(self, data):
                self.buffer = self
                self.data = data
                self.calls = []

            def read(self, count=-1):
                self.calls.append(count)
                if count < 0:
                    raise AssertionError("unbounded read")
                return self.data[:count]

        stream = BinaryStdin(b"{}" + b" " * LIMIT)
        with patch.object(cli.sys, "stdin", stream):
            with self.assertRaises(ValueError):
                cli._load_json(Path("-"))
        self.assertEqual(stream.calls, [LIMIT + 1])

    def test_rejected_input_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / "source.json", root / "wire.avp1"
            source.write_bytes(b"{}" + b" " * LIMIT)
            with self.assertRaises(ValueError):
                cli.main(["encode", str(source), str(destination)])
            self.assertFalse(destination.exists())

    def test_file_path_does_not_use_whole_text_helpers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_bytes(b"{}")
            with patch.object(Path, "read_text", side_effect=AssertionError("whole text read")):
                with patch.object(Path, "read_bytes", side_effect=AssertionError("whole byte read")):
                    self.assertEqual(cli._load_json(path), {})

    def test_small_stdin_pipeline_remains_usable(self):
        with patch.object(cli.sys, "stdin", io.StringIO('{"authority":{}}')):
            with patch.object(cli.sys, "stdout", io.StringIO()) as output:
                self.assertEqual(cli.main(["encode", "-"]), 0)
                self.assertTrue(output.getvalue().startswith("AVP1|"))


if __name__ == "__main__":
    unittest.main()
