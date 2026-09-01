"""Fail-closed verifier for the public ANVIL release boundary."""

from __future__ import annotations

import hashlib
import fnmatch
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".cff", ".css", ".html", ".js", ".json", ".md", ".mjs", ".py", ".toml",
    ".txt", ".yaml", ".yml",
}
TEXT_FILENAMES = {".gitattributes", ".gitignore", "DCO", "LICENSE"}
BINARY_SUFFIXES = {".png"}
ALLOWLIST_PATH = ROOT / "PUBLIC_RELEASE_FILE_ALLOWLIST_V0_1.json"
DENYLIST_PATH = ROOT / "PUBLIC_RELEASE_DENYLIST_V0_1.json"
FORBIDDEN_FINGERPRINTS = (
    (18, "b1d143fcd4befdd77c141eb26d3ab6f8e7cc9f12c4e73bfa95792b2a3fdbe35d"),
    (19, "b8efbf7a82898ff7032a41d7dda617f5a7c26818ea6909e9cb68175cb0c754eb"),
    (25, "2aff26600866f6ffe89dded93c1b1980d63e8a9cae6e955fa450c41b76599353"),
    (17, "bf0d970e058d1920e7c870a277f59616c8830f508a29feab00886c3a7bfb3c6d"),
    (12, "12bc214e5c60594b3f8f28cc56204a03fdd9187295537eba56dfa8d33325efc8"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ignored_generated_path(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return any(
        part in {".git", "__pycache__", ".pytest_cache", "build", "dist"}
        or part.endswith(".egg-info")
        for part in relative.parts
    )


def forbidden_fingerprint(text: str) -> str | None:
    lowered = text.lower()
    for length, expected_digest in FORBIDDEN_FINGERPRINTS:
        for start in range(0, len(lowered) - length + 1):
            candidate = lowered[start : start + length]
            if hashlib.sha256(candidate.encode("utf-8")).hexdigest() == expected_digest:
                return expected_digest
    return None


def load_boundary(path: Path, schema: str) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != schema or value.get("status") != "active":
        raise ValueError(f"invalid release boundary: {path.name}")
    return value


def denied_path(relative: str, globs: list[str]) -> str | None:
    return next((pattern for pattern in globs if fnmatch.fnmatch(relative, pattern)), None)


def denied_text(text: str, fragments: list[str]) -> str | None:
    return next((fragment for fragment in fragments if fragment in text), None)


def main() -> int:
    failures = []
    try:
        allowlist = load_boundary(
            ALLOWLIST_PATH, "anvil-public-release-file-allowlist-v0.1"
        )
        denylist = load_boundary(
            DENYLIST_PATH, "anvil-public-release-denylist-v0.1"
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "failures": [str(exc)]}, indent=2))
        return 1
    files = sorted(
        (
            path
            for path in ROOT.rglob("*")
            if path.is_file() and not ignored_generated_path(path)
        ),
        key=lambda path: path.relative_to(ROOT).as_posix(),
    )
    actual_paths = [
        path.relative_to(ROOT).as_posix()
        for path in files
        if path.name != "RELEASE_MANIFEST.json"
    ]
    expected_paths = allowlist.get("files")
    if (
        not isinstance(expected_paths, list)
        or expected_paths != sorted(set(expected_paths))
        or any(
            not isinstance(path, str)
            or path.startswith("/")
            or ".." in Path(path).parts
            for path in expected_paths
        )
    ):
        failures.append("public release allowlist is noncanonical")
        expected_paths = []
    missing = sorted(set(expected_paths) - set(actual_paths))
    unexpected = sorted(set(actual_paths) - set(expected_paths))
    if missing:
        failures.append(f"allowlisted files missing: {missing}")
    if unexpected:
        failures.append(f"unapproved files present: {unexpected}")

    denied_globs = denylist.get("denied_path_globs")
    denied_fragments = denylist.get("denied_text_fragments")
    if not isinstance(denied_globs, list) or not all(isinstance(row, str) for row in denied_globs):
        failures.append("release path denylist is invalid")
        denied_globs = []
    if not isinstance(denied_fragments, list) or not all(isinstance(row, str) for row in denied_fragments):
        failures.append("release text denylist is invalid")
        denied_fragments = []
    for path in files:
        if path.name == "RELEASE_MANIFEST.json":
            continue
        relative = path.relative_to(ROOT).as_posix()
        matched_path = denied_path(relative, denied_globs)
        if matched_path:
            failures.append(f"denied release path {relative} matched {matched_path}")
        if path.suffix in BINARY_SUFFIXES:
            continue
        if path.suffix not in TEXT_SUFFIXES and path.name not in TEXT_FILENAMES:
            failures.append(
                f"unexpected binary or unsupported file: {path.relative_to(ROOT).as_posix()}"
            )
            continue
        text = path.read_text(encoding="utf-8")
        matched_text = None if path == DENYLIST_PATH else denied_text(text, denied_fragments)
        if matched_text:
            failures.append(
                f"denied internal text fragment in {relative}: {matched_text}"
            )
        matched_fingerprint = None if path == DENYLIST_PATH else forbidden_fingerprint(text)
        if matched_fingerprint:
            failures.append(
                "forbidden private-data fingerprint "
                f"{matched_fingerprint[:12]} in {path.relative_to(ROOT).as_posix()}"
            )

    commands = [
        ("python_codec_conformance", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]),
        ("javascript_codec_conformance", ["node", "tests/test_codec.mjs"]),
    ]
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    checks = []
    for check_id, command in commands:
        result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
        checks.append({"id": check_id, "status": "PASS" if result.returncode == 0 else "FAIL"})
        if result.returncode:
            failures.append(f"check failed: {check_id}")

    manifest = {
        "schema": "anvil-public-beta-release-manifest-v0.2",
        "status": "PASS" if not failures else "FAIL",
        "publication_authority_effect": "none",
        "canonical_name": "Adaptive Neural Vector Instruction Language",
        "profile": "AVP1/governed-mission-v1",
        "allowlist_sha256": sha256(ALLOWLIST_PATH),
        "denylist_sha256": sha256(DENYLIST_PATH),
        "files": [
            {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)}
            for path in files
            if path.name != "RELEASE_MANIFEST.json"
        ],
        "checks": checks,
        "failures": failures,
    }
    (ROOT / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "files": len(manifest["files"]), "failures": failures}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
