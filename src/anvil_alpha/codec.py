"""Dependency-free, exact, context-bound ANVIL public reference profile.

AVP1 is intentionally smaller and simpler than the private experimental AVD2
profile. It demonstrates the public contract: deterministic canonicalization,
reversible compact symbols, an explicit profile binding, and exact authority
preservation. It does not reproduce or claim AVD2's historical compression.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping


class CodecError(ValueError):
    """Raised when an AVP1 message is malformed or non-canonical."""


class ContextMismatchError(CodecError):
    """Raised when a message is decoded with the wrong signed profile."""


PROFILE_ID = "governed-mission-v1"
WIRE_PREFIX = "AVP1"

KEYS = (
    "version",
    "mission",
    "inputs",
    "steps",
    "outputs",
    "authority",
    "name",
    "type",
    "ref",
    "op",
    "bind",
    "args",
    "effects",
    "permits",
    "forbids",
    "requirements",
    "kind",
    "target",
    "gate",
    "approval",
    "evidence",
    "mode",
    "effect",
    "condition",
    "value",
    "count",
    "require",
)

VALUES = (
    "0.1",
    "read",
    "write",
    "publish",
    "human",
    "exact_text",
    "gate",
    "approval",
    "source",
    "staging",
    "posts",
    "pass",
    "fox_pass",
)

KEY_TO_SYMBOL = {key: f"@{index:x}" for index, key in enumerate(KEYS)}
SYMBOL_TO_KEY = {symbol: key for key, symbol in KEY_TO_SYMBOL.items()}
VALUE_TO_SYMBOL = {value: f"#{index:x}" for index, value in enumerate(VALUES)}
SYMBOL_TO_VALUE = {symbol: value for value, symbol in VALUE_TO_SYMBOL.items()}


def _reject_constant(value: str) -> None:
    raise CodecError(f"non-finite JSON number is not supported: {value}")


def normalize(value: Any) -> Any:
    """Return a JSON-only value with deterministic object ordering."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise CodecError("non-finite JSON numbers are not supported")
        return value
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, Mapping):
        normalized = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise CodecError("JSON object keys must be strings")
            normalized[key] = normalize(value[key])
        return normalized
    raise CodecError(f"unsupported JSON type: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        normalize(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def semantic_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _encode_key(key: str) -> str:
    if key in KEY_TO_SYMBOL:
        return KEY_TO_SYMBOL[key]
    return "@" + key if key.startswith("@") else key


def _decode_key(key: str) -> str:
    if key in SYMBOL_TO_KEY:
        return SYMBOL_TO_KEY[key]
    return key[1:] if key.startswith("@@") else key


def _pack(value: Any) -> Any:
    if isinstance(value, str):
        if value in VALUE_TO_SYMBOL:
            return VALUE_TO_SYMBOL[value]
        return "#" + value if value.startswith("#") else value
    if isinstance(value, list):
        return [_pack(item) for item in value]
    if isinstance(value, dict):
        return {_encode_key(key): _pack(item) for key, item in value.items()}
    return value


def _unpack(value: Any) -> Any:
    if isinstance(value, str):
        if value in SYMBOL_TO_VALUE:
            return SYMBOL_TO_VALUE[value]
        return value[1:] if value.startswith("##") else value
    if isinstance(value, list):
        return [_unpack(item) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            decoded_key = _decode_key(key)
            if decoded_key in result:
                raise CodecError(f"decoded key collision: {decoded_key!r}")
            result[decoded_key] = _unpack(item)
        return result
    return value


@dataclass(frozen=True)
class AVP1Codec:
    profile_id: str = PROFILE_ID

    def encode(self, value: Any) -> str:
        normalized = normalize(value)
        body = json.dumps(
            _pack(normalized),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"{WIRE_PREFIX}|{self.profile_id}|{body}"

    def decode(self, wire: str) -> Any:
        parts = wire.split("|", 2)
        if len(parts) != 3 or parts[0] != WIRE_PREFIX:
            raise CodecError("invalid AVP1 wire header")
        if parts[1] != self.profile_id:
            raise ContextMismatchError(
                f"profile mismatch: expected {self.profile_id!r}, got {parts[1]!r}"
            )
        try:
            packed = json.loads(parts[2], parse_constant=_reject_constant)
        except json.JSONDecodeError as exc:
            raise CodecError(f"invalid AVP1 JSON body: {exc.msg}") from exc
        decoded = normalize(_unpack(packed))
        if self.encode(decoded) != wire:
            raise CodecError("AVP1 message is valid but non-canonical")
        return decoded

    def verify(self, source: Any, wire: str) -> bool:
        return canonical_json(source) == canonical_json(self.decode(wire))
