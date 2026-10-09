#!/usr/bin/env python3
"""Offline, fresh-process reproduction of the draft-survived demonstration."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


BEFORE = "def average(values):\n    return sum(values) / len(values)\n"
AFTER = "def average(values):\n    if not values: return 0\n    return sum(values) / len(values)\n"


def workbench():
    spec = importlib.util.spec_from_file_location("anvil_demo_workbench", Path(__file__).with_name("workbench.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def stage(name, root):
    wb = workbench()
    checkpoint = root / "draft.anvil-checkpoint.json"
    if name == "save":
        class RecordedCompletion:
            def complete(self, *args, **kwargs):
                return {"complete": True, "text": AFTER}
        session = wb.ProposalSession(RecordedCompletion())
        proposal = session.propose({"file": str(root / "work.py"), "instruction": "Return zero for an empty list."})
        assert proposal["reviewable"] and not proposal["applied"]
        session.save_checkpoint(proposal["proposal_id"], root, checkpoint)
        assert (root / "work.py").read_text() == BEFORE
        return {"saved": True, "new_model_requests": 0, "input": "recorded candidate", "applied": False}
    session = wb.ProposalSession(wb.OfflineCompletion())
    if name == "recover":
        proposal = session.load_checkpoint(checkpoint, root)
        session.export_patch(proposal["proposal_id"], root, root / "recovered.patch")
        assert (root / "work.py").read_text() == BEFORE
        return {"restored": True, "new_model_requests": proposal["model_requests"], "applied": False}
    if name == "stale":
        try:
            session.load_checkpoint(checkpoint, root)
        except ValueError as exc:
            if "source changed" not in str(exc):
                raise
            return {"changed_target_refused": True, "reason": str(exc)}
        raise AssertionError("Changed source must be refused")
    raise ValueError(name)


def child(name, root):
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--stage", name, "--root", str(root)],
                            check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def run_demo():
    if not shutil.which("git"):
        raise RuntimeError("Git is required for the throwaway patch check")
    with tempfile.TemporaryDirectory(prefix="anvil-draft-demo-") as temporary:
        root = Path(temporary)
        (root / "work.py").write_text(BEFORE)
        (root / "shop.json").write_text('{"pickup": "Friday"}\n')
        saved = child("save", root)  # This process exits before the other edit.
        (root / "shop.json").write_text('{"pickup": "Saturday"}\n')
        recovered = child("recover", root)  # A separate offline process.
        assert (root / "shop.json").read_text() == '{"pickup": "Saturday"}\n'
        sandbox = root / "throwaway"
        sandbox.mkdir()
        shutil.copy(root / "work.py", sandbox / "work.py")
        shutil.copy(root / "shop.json", sandbox / "shop.json")
        patch = root / "recovered.patch"
        subprocess.run(["git", "apply", "--check", str(patch)], cwd=sandbox, check=True, capture_output=True)
        subprocess.run(["git", "apply", str(patch)], cwd=sandbox, check=True, capture_output=True)
        checks = subprocess.run([sys.executable, "-c",
            "from work import average; assert average([]) == 0; assert average([2,4]) == 3; assert average([-2,2]) == 0"],
            cwd=sandbox, check=True, capture_output=True)
        assert (sandbox / "work.py").read_text() == AFTER
        assert (sandbox / "shop.json").read_bytes() == (root / "shop.json").read_bytes()
        assert (root / "work.py").read_text() == BEFORE
        (root / "work.py").write_text(BEFORE + "# another edit in the target file\n")
        stale = child("stale", root)
        return {"schema": "anvil-session-demo-v1", "save": saved, "recovery": recovered,
                "separate_file_edit_preserved": True, "git_apply_check_passed": True,
                "behavior_checks_passed": 3, "patch_applied_only_to_throwaway_copy": True,
                "changed_target": stale, "human_approval": "not granted by this demonstration",
                "candidate_sha256": hashlib.sha256(AFTER.encode()).hexdigest(),
                "limits": ["recorded candidate, not fresh model inference", "scripted separate-file edit",
                           "one fixture", "source hashes are point-in-time checks, not locks or authentication"]}


def main():
    if sys.flags.optimize:
        raise RuntimeError("Run without Python -O so acceptance assertions remain active")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["save", "recover", "stale"], help=argparse.SUPPRESS)
    parser.add_argument("--root", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--receipt", type=Path, help="Write the outcome to a new file outside the checkout")
    args = parser.parse_args()
    result = stage(args.stage, args.root) if args.stage else run_demo()
    data = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.receipt:
        with args.receipt.open("x", encoding="utf-8") as stream:
            stream.write(data)
    print(data, end="")


if __name__ == "__main__":
    main()
