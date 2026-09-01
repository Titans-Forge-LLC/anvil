"""Command-line interface for the public AVP1 reference profile."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .codec import AVP1Codec, canonical_json, semantic_sha256


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path | None, text: str) -> None:
    if path is None:
        print(text)
    else:
        path.write_text(text + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="anvil")
    subparsers = parser.add_subparsers(dest="command", required=True)

    encode = subparsers.add_parser("encode", help="encode canonical JSON to AVP1")
    encode.add_argument("input", type=Path)
    encode.add_argument("output", type=Path, nargs="?")

    decode = subparsers.add_parser("decode", help="decode AVP1 to canonical JSON")
    decode.add_argument("input", type=Path)
    decode.add_argument("output", type=Path, nargs="?")

    verify = subparsers.add_parser("verify", help="verify an exact semantic round trip")
    verify.add_argument("source", type=Path)
    verify.add_argument("wire", type=Path)

    benchmark = subparsers.add_parser("benchmark", help="report exact byte counts")
    benchmark.add_argument("input", type=Path)

    args = parser.parse_args(argv)
    codec = AVP1Codec()

    if args.command == "encode":
        _write(args.output, codec.encode(_load_json(args.input)))
        return 0
    if args.command == "decode":
        decoded = codec.decode(args.input.read_text(encoding="utf-8").strip())
        _write(args.output, json.dumps(decoded, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "verify":
        source = _load_json(args.source)
        wire = args.wire.read_text(encoding="utf-8").strip()
        decoded = codec.decode(wire)
        exact = canonical_json(source) == canonical_json(decoded)
        authority_exact = semantic_sha256(source.get("authority")) == semantic_sha256(
            decoded.get("authority")
        )
        print(json.dumps({
            "semantic_exact": exact,
            "authority_exact": authority_exact,
            "semantic_sha256": semantic_sha256(decoded),
            "authority_sha256": semantic_sha256(decoded.get("authority")),
        }, indent=2, sort_keys=True))
        return 0 if exact and authority_exact else 1
    if args.command == "benchmark":
        source = _load_json(args.input)
        canonical = canonical_json(source).encode("utf-8")
        wire = codec.encode(source).encode("utf-8")
        print(json.dumps({
            "profile": codec.profile_id,
            "canonical_json_bytes": len(canonical),
            "avp1_wire_bytes": len(wire),
            "compression_ratio": round(len(canonical) / len(wire), 4),
            "semantic_exact": codec.verify(source, wire.decode("utf-8")),
        }, indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
