from __future__ import annotations

import importlib.util
import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_release", ROOT / "scripts" / "verify_release.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ReleaseBoundaryTests(unittest.TestCase):
    def test_no_function_tests_silently_skipped_by_unittest(self) -> None:
        for path in (ROOT / "tests").glob("test_*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            skipped = [node.name for node in tree.body
                       if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and node.name.startswith("test_")]
            self.assertEqual(skipped, [], f"unittest would skip tests in {path.name}")

    def test_private_artifact_classes_are_denied(self) -> None:
        globs = MODULE.load_boundary(
            MODULE.DENYLIST_PATH, "anvil-public-release-denylist-v0.1"
        )["denied_path_globs"]
        for path in (
            "data/state.sqlite",
            "weights/model.safetensors",
            "filing/private.pdf",
            "secrets/operator.pem",
            "results/retired-shadow.json",
        ):
            self.assertIsNotNone(MODULE.denied_path(path, globs), path)

    def test_internal_absolute_paths_are_denied(self) -> None:
        fragments = MODULE.load_boundary(
            MODULE.DENYLIST_PATH, "anvil-public-release-denylist-v0.1"
        )["denied_text_fragments"]
        self.assertEqual(
            MODULE.denied_text(f"open {fragments[0]}private", fragments),
            fragments[0],
        )

    def test_allowlist_is_sorted_unique_and_contains_boundary_files(self) -> None:
        files = MODULE.load_boundary(
            MODULE.ALLOWLIST_PATH, "anvil-public-release-file-allowlist-v0.1"
        )["files"]
        self.assertEqual(files, sorted(set(files)))
        self.assertIn("PUBLIC_RELEASE_FILE_ALLOWLIST_V0_1.json", files)
        self.assertIn("PUBLIC_RELEASE_DENYLIST_V0_1.json", files)


if __name__ == "__main__":
    unittest.main()
