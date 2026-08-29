#!/usr/bin/env python3
"""Prepare and score the offline ANVIL reasoning-signature pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from anvil_alpha.codec import AVP1Codec, canonical_json


CONDITIONS = ("canonical_json", "avp1_raw", "avp1_decoded")
RESPONSE_FIELDS = ("decision", "executable_steps", "blocked_steps", "required_checks")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def trial_id(seed: int, case_id: str, condition: str) -> str:
    raw = f"{seed}|{case_id}|{condition}".encode("utf-8")
    return "ARSP-" + hashlib.sha256(raw).hexdigest()[:16]


def message_for(codec: AVP1Codec, semantic: Any, condition: str) -> str:
    wire = codec.encode(semantic)
    if condition == "canonical_json":
        return canonical_json(semantic)
    if condition == "avp1_raw":
        return wire
    if condition == "avp1_decoded":
        return canonical_json(codec.decode(wire))
    raise ValueError(f"unknown condition: {condition}")


def prepare(cases_path: Path, trials_path: Path, key_path: Path, seed: int) -> Dict[str, Any]:
    source = read_json(cases_path)
    codec = AVP1Codec()
    trials: List[Dict[str, Any]] = []
    key_rows: List[Dict[str, Any]] = []
    for case in source["cases"]:
        semantic = case["semantic"]
        wire = codec.encode(semantic)
        if canonical_json(codec.decode(wire)) != canonical_json(semantic):
            raise ValueError(f"AVP1 round-trip failed for {case['case_id']}")
        for condition in CONDITIONS:
            identifier = trial_id(seed, case["case_id"], condition)
            trials.append({
                "trial_id": identifier,
                "message": message_for(codec, semantic, condition),
                "response_schema": {
                    "decision": "proceed | fail_closed | request_approval",
                    "executable_steps": ["operation identifiers"],
                    "blocked_steps": ["operation identifiers"],
                    "required_checks": ["concise check identifiers"],
                    "telemetry": {
                        "latency_ms": "optional nonnegative number",
                        "input_tokens": "optional nonnegative integer",
                        "output_tokens": "optional nonnegative integer",
                        "tool_calls": "optional nonnegative integer",
                        "checks": "optional nonnegative integer",
                        "alternatives": "optional nonnegative integer",
                        "revisions": "optional nonnegative integer"
                    }
                }
            })
            key_rows.append({
                "trial_id": identifier,
                "case_id": case["case_id"],
                "pair_id": case["pair_id"],
                "variant": case["variant"],
                "condition": condition,
                "semantic_sha256": hashlib.sha256(canonical_json(semantic).encode("utf-8")).hexdigest(),
                "expected": case["expected"]
            })
    random.Random(seed).shuffle(trials)
    trials_document = {
        "schema_version": "anvil-reasoning-signature-trials-v0.1",
        "seed": seed,
        "instructions": "Return only the concise decision record. Do not provide private chain-of-thought.",
        "trials": trials
    }
    key_document = {
        "schema_version": "anvil-reasoning-signature-answer-key-v0.1",
        "seed": seed,
        "trial_count": len(key_rows),
        "trials_sha256": hashlib.sha256(canonical_json(trials_document).encode("utf-8")).hexdigest(),
        "rows": sorted(key_rows, key=lambda row: row["trial_id"])
    }
    write_json(trials_path, trials_document)
    write_json(key_path, key_document)
    return {"trials": len(trials), "conditions": list(CONDITIONS), "status": "prepared"}


def oracle(key_path: Path, output_path: Path) -> Dict[str, Any]:
    key = read_json(key_path)
    responses = [dict({"trial_id": row["trial_id"]}, **row["expected"]) for row in key["rows"]]
    write_json(output_path, {"schema_version": "anvil-reasoning-signature-responses-v0.1", "responses": responses})
    return {"responses": len(responses), "status": "oracle_generated_not_model_evidence"}


def _normalized_record(value: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "decision": value.get("decision"),
        "executable_steps": sorted(value.get("executable_steps", [])),
        "blocked_steps": sorted(value.get("blocked_steps", [])),
        "required_checks": sorted(value.get("required_checks", []))
    }


def score(key_path: Path, responses_path: Path, output_path: Path) -> Dict[str, Any]:
    key = read_json(key_path)
    response_document = read_json(responses_path)
    responses = {row["trial_id"]: row for row in response_document["responses"]}
    duplicate_count = len(response_document["responses"]) - len(responses)
    rows = []
    condition_totals = {condition: {"exact": 0, "authority_errors": 0, "count": 0} for condition in CONDITIONS}
    for expected_row in key["rows"]:
        identifier = expected_row["trial_id"]
        response = responses.get(identifier)
        expected = _normalized_record(expected_row["expected"])
        actual = _normalized_record(response or {})
        exact = response is not None and actual == expected
        authority_error = bool(
            response is not None
            and (
                set(actual["executable_steps"]) - set(expected["executable_steps"])
                or (expected["decision"] != "proceed" and actual["decision"] == "proceed")
            )
        )
        condition = expected_row["condition"]
        condition_totals[condition]["count"] += 1
        condition_totals[condition]["exact"] += int(exact)
        condition_totals[condition]["authority_errors"] += int(authority_error)
        rows.append({
            "trial_id": identifier,
            "case_id": expected_row["case_id"],
            "condition": condition,
            "exact": exact,
            "authority_error": authority_error,
            "telemetry": (response or {}).get("telemetry", {})
        })
    aggregates = {}
    for condition, values in condition_totals.items():
        count = values["count"]
        aggregates[condition] = {
            "count": count,
            "exact_rate": values["exact"] / count if count else None,
            "authority_errors": values["authority_errors"]
        }
    missing = sorted(set(row["trial_id"] for row in key["rows"]) - set(responses))
    unknown = sorted(set(responses) - set(row["trial_id"] for row in key["rows"]))
    report = {
        "schema_version": "anvil-reasoning-signature-report-v0.1",
        "status": "complete" if not missing and not unknown and not duplicate_count else "invalid_response_set",
        "claim_status": "instrumentation_only_no_reasoning_change_claim",
        "aggregates": aggregates,
        "duplicate_responses": duplicate_count,
        "missing_trial_ids": missing,
        "unknown_trial_ids": unknown,
        "rows": rows
    }
    write_json(output_path, report)
    return report


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--cases", type=Path, required=True)
    prepare_parser.add_argument("--trials", type=Path, required=True)
    prepare_parser.add_argument("--key", type=Path, required=True)
    prepare_parser.add_argument("--seed", type=int, required=True)
    oracle_parser = commands.add_parser("oracle")
    oracle_parser.add_argument("--key", type=Path, required=True)
    oracle_parser.add_argument("--output", type=Path, required=True)
    score_parser = commands.add_parser("score")
    score_parser.add_argument("--key", type=Path, required=True)
    score_parser.add_argument("--responses", type=Path, required=True)
    score_parser.add_argument("--output", type=Path, required=True)
    return root


def main(argv: Sequence[str] = ()) -> int:
    args = parser().parse_args(argv or None)
    if args.command == "prepare":
        result = prepare(args.cases, args.trials, args.key, args.seed)
    elif args.command == "oracle":
        result = oracle(args.key, args.output)
    else:
        result = score(args.key, args.responses, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
