import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "run_reasoning_signature_ollama.py"
SPEC = importlib.util.spec_from_file_location("run_reasoning_signature_ollama", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ReasoningSignatureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp_path = Path(temporary.name)

    def test_runner_never_receives_key_and_does_not_store_thinking(self):
        tmp_path = self.tmp_path
        trials = {
            "schema_version": "test",
            "trials": [{"trial_id": "blind-1", "message": "{}"}]
        }
        trials_path = tmp_path / "trials.json"
        output = tmp_path / "responses.json"
        trials_path.write_text(json.dumps(trials), encoding="utf-8")

        def fake_post(url, payload, timeout):
            serialized = json.dumps(payload).casefold()
            assert '"expected"' not in serialized
            assert '"condition"' not in serialized
            assert payload["think"] is False
            return {
                "message": {
                    "content": json.dumps({
                        "decision": "fail_closed",
                        "executable_steps": [],
                        "blocked_steps": [],
                        "required_checks": []
                    }),
                    "thinking": "must never be stored"
                },
                "prompt_eval_count": 10,
                "eval_count": 5
            }

        original = MODULE.post_json
        self.addCleanup(setattr, MODULE, "post_json", original)
        MODULE.post_json = fake_post
        result = MODULE.run(trials_path, "test-model", output, "http://127.0.0.1:11434", 17, 1)
        assert result["errors"] == 0
        stored = output.read_text(encoding="utf-8")
        assert "must never be stored" not in stored
        assert json.loads(stored)["private_chain_of_thought_stored"] is False


    def test_runner_refuses_overwrite(self):
        tmp_path = self.tmp_path
        trials = tmp_path / "trials.json"
        output = tmp_path / "responses.json"
        trials.write_text('{"trials": []}', encoding="utf-8")
        output.write_text("existing", encoding="utf-8")
        try:
            MODULE.run(trials, "test-model", output, "http://127.0.0.1:11434", 17, 1)
        except FileExistsError:
            pass
        else:
            raise AssertionError("runner overwrote an immutable result")
