"""CLI output-integrity checks and post-campaign integration regressions.

These public tests do not revise the frozen private editing-job acceptance
suite or its results. Passing them is not proof of crash durability or freedom
from concurrent filesystem races.
"""
import builtins
from contextlib import ExitStack, redirect_stdout
import errno
import io
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from anvil_alpha.cli import _write


class PartialWriteFailure:
    """Write a real prefix to scratch, then raise a deterministic I/O failure."""

    def __init__(self, stream, events):
        self.stream, self.events = stream, events

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def __enter__(self):
        self.stream.__enter__()
        return self

    def __exit__(self, *args):
        return self.stream.__exit__(*args)

    def write(self, value):
        self.events.append("partial_stream_write")
        if value:
            self.stream.write(value[:3])
            self.stream.flush()
        raise OSError("partial-write fault")

    def writelines(self, values):
        for value in values:
            self.write(value)


class AtomicOutputTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="atomic-output-test-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.destination = self.root / "output.txt"
        self.sentinel = b"existing-output-must-survive\n"
        self.destination.write_bytes(self.sentinel)

    def assert_only_destination(self):
        self.assertEqual(set(self.root.iterdir()), {self.destination})

    def test_existing_output_survives_utf8_encoding_failure(self):
        with self.assertRaises(UnicodeError):
            _write(self.destination, "not-encodable-\ud800")
        self.assertEqual(self.destination.read_bytes(), self.sentinel)
        self.assert_only_destination()

    def test_new_output_absent_after_utf8_encoding_failure(self):
        target = self.root / "new.txt"
        with self.assertRaises(UnicodeError):
            _write(target, "not-encodable-\udfff")
        self.assertFalse(target.exists())
        self.assert_only_destination()

    def test_existing_output_survives_partial_write_failure(self):
        events = []
        original_builtin_open, original_io_open = builtins.open, io.open
        original_fdopen, original_write = os.fdopen, os.write

        def wrap_open(original):
            def open_with_fault(file, mode="r", *args, **kwargs):
                stream = original(file, mode, *args, **kwargs)
                if any(character in mode for character in "wax+"):
                    return PartialWriteFailure(stream, events)
                return stream
            return open_with_fault

        def write_with_fault(fd, value):
            events.append("partial_descriptor_write")
            if value:
                original_write(fd, value[:3])
            raise OSError("partial-write fault")

        with ExitStack() as stack:
            stack.enter_context(patch("builtins.open", side_effect=wrap_open(original_builtin_open)))
            stack.enter_context(patch("io.open", side_effect=wrap_open(original_io_open)))
            stack.enter_context(patch("os.fdopen", side_effect=wrap_open(original_fdopen)))
            stack.enter_context(patch("os.write", side_effect=write_with_fault))
            with self.assertRaises(OSError):
                _write(self.destination, "replacement-content")
        self.assertTrue(events, "fault injection must exercise an actual write")
        self.assertEqual(self.destination.read_bytes(), self.sentinel)
        self.assert_only_destination()

    def test_existing_output_survives_replace_failure(self):
        with patch("os.replace", side_effect=OSError("replacement fault")) as replace:
            with self.assertRaises(OSError):
                _write(self.destination, "replacement-content")
            self.assertTrue(replace.called)
        self.assertEqual(self.destination.read_bytes(), self.sentinel)
        self.assert_only_destination()

    def test_new_output_absent_after_replace_failure(self):
        target = self.root / "new.txt"
        with patch("os.replace", side_effect=OSError("replacement fault")):
            with self.assertRaises(OSError):
                _write(target, "replacement-content")
        self.assertFalse(target.exists())
        self.assert_only_destination()

    def test_unicode_and_newline_behavior_for_existing_and_new_files(self):
        for index, text in enumerate(("", "hello", "hello\n", "hello\n\n", "café 🛠", "x\r\n")):
            expected = text if text.endswith("\n") else text + "\n"
            expected_bytes = expected.replace("\n", os.linesep).encode("utf-8")
            with self.subTest(text=text):
                _write(self.destination, text)
                self.assertEqual(self.destination.read_bytes(), expected_bytes)
                new_path = self.root / ("new-" + str(index) + ".txt")
                _write(new_path, text)
                self.assertEqual(new_path.read_bytes(), expected_bytes)
                new_path.unlink()
                self.assert_only_destination()

    def test_stdout_behavior_for_none_and_dash(self):
        for target in (None, Path("-")):
            for text in ("", "hello", "hello\n", "hello\n\n", "café 🛠", "x\r\n"):
                expected = text if text.endswith("\n") else text + "\n"
                with self.subTest(target=target, text=text), redirect_stdout(io.StringIO()) as output:
                    _write(target, text)
                self.assertEqual(output.getvalue(), expected)
        self.assertEqual(self.destination.read_bytes(), self.sentinel)
        self.assert_only_destination()

    def test_preserves_regular_destination_permission_bits(self):
        if os.name != "posix":
            self.skipTest("POSIX permission bits are not portable to Windows")
        self.destination.chmod(0o640)
        _write(self.destination, "updated")
        self.assertEqual(stat.S_IMODE(self.destination.stat().st_mode), 0o640)
        self.assertEqual(self.destination.read_bytes(), b"updated\n")
        self.assert_only_destination()

    def test_rejects_existing_and_dangling_symlink_destinations(self):
        for target_name in ("output.txt", "nonexistent.txt"):
            link = self.root / "link.txt"
            try:
                link.symlink_to(target_name)
            except (OSError, NotImplementedError) as error:
                if os.name == "nt":
                    self.skipTest("Windows symlink creation unavailable: " + str(error))
                raise
            with self.subTest(target=target_name), self.assertRaises((OSError, ValueError)):
                _write(link, "must-not-follow-or-replace-link")
            self.assertTrue(link.is_symlink())
            self.assertEqual(os.readlink(link), target_name)
            self.assertEqual(self.destination.read_bytes(), self.sentinel)
            self.assertFalse((self.root / "nonexistent.txt").exists())
            self.assertEqual(set(self.root.iterdir()), {self.destination, link})
            link.unlink()

    def test_file_stream_keeps_platform_native_newline_translation(self):
        # On macOS newline='' happens to produce the same bytes as newline=None.
        # Guard the setting here; the byte-level test above also runs on Windows.
        original_fdopen = os.fdopen
        newline_arguments = []

        def observe_fdopen(*args, **kwargs):
            newline_arguments.append(kwargs.get("newline", args[5] if len(args) > 5 else None))
            return original_fdopen(*args, **kwargs)

        with patch("os.fdopen", side_effect=observe_fdopen):
            _write(self.destination, "line one\nline two")
        self.assertTrue(newline_arguments)
        self.assertTrue(all(value is None for value in newline_arguments))
        self.assertEqual(self.destination.read_bytes(),
                         ("line one\nline two\n").replace("\n", os.linesep).encode("utf-8"))
        self.assert_only_destination()

    def test_missing_parent_is_not_created(self):
        parent = self.root / "missing" / "nested"
        with self.assertRaises(FileNotFoundError):
            _write(parent / "new.txt", "content")
        self.assertFalse((self.root / "missing").exists())
        self.assertEqual(self.destination.read_bytes(), self.sentinel)
        self.assert_only_destination()

    def test_fdopen_failure_closes_owned_descriptor_and_removes_temporary_file(self):
        original_mkstemp = tempfile.mkstemp
        allocated = []

        def record_mkstemp(*args, **kwargs):
            result = original_mkstemp(*args, **kwargs)
            allocated.append(result)
            return result

        error = OSError("stream construction fault")
        with patch("tempfile.mkstemp", side_effect=record_mkstemp), \
                patch("os.fdopen", side_effect=error):
            with self.assertRaises(OSError) as caught:
                _write(self.destination, "replacement-content")
        self.assertIs(caught.exception, error)
        self.assertEqual(len(allocated), 1)
        for fd, path in allocated:
            with self.assertRaises(OSError) as closed:
                os.fstat(fd)
            self.assertEqual(closed.exception.errno, errno.EBADF)
            self.assertFalse(Path(path).exists())
        self.assertEqual(self.destination.read_bytes(), self.sentinel)
        self.assert_only_destination()

    def test_destination_metadata_failures_are_not_treated_as_absence(self):
        # Path.lstat delegates to stat(..., follow_symlinks=False). Test both
        # entry points so only FileNotFoundError is accepted as ordinary absence.
        for lookup in ("stat", "lstat"):
            for error in (PermissionError("metadata permission fault"),
                          OSError(errno.EIO, "metadata I/O fault")):
                original_lookup = getattr(Path, lookup)

                def fail_destination(path, *args, **kwargs):
                    if path == self.destination:
                        raise error
                    return original_lookup(path, *args, **kwargs)

                with self.subTest(lookup=lookup, error=type(error).__name__):
                    with patch.object(Path, lookup, autospec=True, side_effect=fail_destination):
                        with self.assertRaises(OSError) as caught:
                            _write(self.destination, "replacement-content")
                    self.assertIs(caught.exception, error)
                    self.assertEqual(self.destination.read_bytes(), self.sentinel)
                    self.assert_only_destination()

    def test_directory_destination_is_refused_without_changes(self):
        directory = self.root / "directory"
        directory.mkdir()
        member = directory / "keep.txt"
        member.write_bytes(self.sentinel)
        with self.assertRaises((OSError, ValueError)):
            _write(directory, "must-not-replace-directory")
        self.assertTrue(directory.is_dir())
        self.assertEqual(set(directory.iterdir()), {member})
        self.assertEqual(member.read_bytes(), self.sentinel)
        self.assertEqual(self.destination.read_bytes(), self.sentinel)
        self.assertEqual(set(self.root.iterdir()), {self.destination, directory})


if __name__ == "__main__":
    unittest.main()
