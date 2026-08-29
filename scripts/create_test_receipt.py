"""Create a privacy-bounded independent-test receipt for the AVP1 reference."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from anvil_alpha import AVP1Codec, canonical_json
from anvil_alpha.codec import semantic_sha256


ROOT = Path(__file__).resolve().parents[1]


def command_result(command: list[str]) -> dict[str, object]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "returncode": result.returncode,
    }


def git_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True
    )
    return result.stdout.strip() if result.returncode == 0 else None


def node_version() -> str | None:
    result = subprocess.run(
        ["node", "--version"], cwd=ROOT, text=True, capture_output=True
    )
    return result.stdout.strip() if result.returncode == 0 else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    python_check = command_result(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]
    )
    javascript_check = command_result(["node", "tests/test_codec.mjs"])

    source = json.loads((ROOT / "examples/governed_mission.json").read_text(encoding="utf-8"))
    codec = AVP1Codec()
    wire = codec.encode(source)
    decoded = codec.decode(wire)
    canonical = canonical_json(source)
    semantic_exact = canonical == canonical_json(decoded)
    authority_exact = source.get("authority") == decoded.get("authority")
    status = (
        "PASS"
        if python_check["status"] == javascript_check["status"] == "PASS"
        and semantic_exact
        and authority_exact
        else "FAIL"
    )

    receipt = {
        "schema": "anvil-open-reference-test-receipt-v0.1",
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "repository": "https://github.com/Titans-Forge-LLC/anvil",
            "commit": git_commit(),
            "profile": codec.profile_id,
        },
        "environment": {
            "operating_system": platform.system(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "node": node_version(),
        },
        "checks": {
            "python_conformance": python_check,
            "javascript_conformance": javascript_check,
            "semantic_exact": semantic_exact,
            "authority_exact": authority_exact,
        },
        "measurement": {
            "canonical_json_bytes": len(canonical.encode("utf-8")),
            "avp1_wire_bytes": len(wire.encode("utf-8")),
            "compression_ratio": round(
                len(canonical.encode("utf-8")) / len(wire.encode("utf-8")), 4
            ),
            "wire_sha256": hashlib.sha256((wire + "\n").encode("utf-8")).hexdigest(),
            "wire_hash_scope": "UTF-8 CLI wire file including its final LF",
            "wire_payload_sha256": hashlib.sha256(wire.encode("utf-8")).hexdigest(),
            "semantic_sha256": semantic_sha256(decoded),
            "authority_sha256": semantic_sha256(decoded.get("authority")),
        },
        "privacy": {
            "contains_hostname": False,
            "contains_username": False,
            "contains_filesystem_paths": False,
            "contains_source_payload": False,
        },
        "claim_boundary": (
            "This receipt records one environment's public-reference reproduction; "
            "it is not production, security, patent, or universal-compression evidence."
        ),
    }

    output = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
