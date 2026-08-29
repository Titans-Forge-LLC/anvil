"""Fail-closed release-candidate verifier for the public ANVIL directory."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".cff", ".css", ".html", ".js", ".json", ".md", ".mjs", ".py", ".toml",
    ".txt", ".yaml", ".yml",
}
TEXT_FILENAMES = {".gitignore", "DCO", "LICENSE"}
BINARY_SUFFIXES = {".png"}
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


def main() -> int:
    failures = []
    files = sorted(
        path for path in ROOT.rglob("*")
        if path.is_file() and not ignored_generated_path(path)
    )
    for path in files:
        if path.suffix in BINARY_SUFFIXES:
            continue
        if path.suffix not in TEXT_SUFFIXES and path.name not in TEXT_FILENAMES:
            failures.append(f"unexpected binary or unsupported file: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        matched_fingerprint = forbidden_fingerprint(text)
        if matched_fingerprint:
            failures.append(
                f"forbidden private-data fingerprint {matched_fingerprint[:12]} in {path.relative_to(ROOT)}"
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
        "schema": "anvil-public-alpha-release-manifest-v0.1",
        "status": "PASS" if not failures else "FAIL",
        "publication_authorized": False,
        "canonical_name": "Adaptive Neural Vector Instruction Language",
        "profile": "AVP1/governed-mission-v1",
        "files": [{"path": str(path.relative_to(ROOT)), "sha256": sha256(path)} for path in files if path.name != "RELEASE_MANIFEST.json"],
        "checks": checks,
        "failures": failures,
    }
    (ROOT / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "files": len(manifest["files"]), "failures": failures}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
