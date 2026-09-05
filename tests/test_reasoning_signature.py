import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "reasoning_signature.py"
SPEC = importlib.util.spec_from_file_location("reasoning_signature", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ReasoningSignatureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp_path = Path(temporary.name)

    def test_three_condition_pack_roundtrips_and_scores(self):
        tmp_path = self.tmp_path
        trials = tmp_path / "trials.json"
        key = tmp_path / "key.json"
        responses = tmp_path / "responses.json"
        report = tmp_path / "report.json"
        result = MODULE.prepare(
            ROOT / "experiments" / "reasoning-signature" / "cases.json",
            trials,
            key,
            17,
        )
        assert result["trials"] == 12
        MODULE.oracle(key, responses)
        scored = MODULE.score(key, responses, report)
        assert scored["status"] == "complete"
        assert scored["claim_status"] == "instrumentation_only_no_reasoning_change_claim"
        assert all(row["exact_rate"] == 1.0 for row in scored["aggregates"].values())
        assert all(row["authority_errors"] == 0 for row in scored["aggregates"].values())


    def test_missing_response_invalidates_set(self):
        tmp_path = self.tmp_path
        trials = tmp_path / "trials.json"
        key = tmp_path / "key.json"
        responses = tmp_path / "responses.json"
        report = tmp_path / "report.json"
        MODULE.prepare(ROOT / "experiments" / "reasoning-signature" / "cases.json", trials, key, 29)
        MODULE.oracle(key, responses)
        document = json.loads(responses.read_text(encoding="utf-8"))
        document["responses"].pop()
        responses.write_text(json.dumps(document), encoding="utf-8")
        scored = MODULE.score(key, responses, report)
        assert scored["status"] == "invalid_response_set"
        assert len(scored["missing_trial_ids"]) == 1
