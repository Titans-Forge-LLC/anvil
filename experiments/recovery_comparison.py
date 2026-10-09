#!/usr/bin/env python3
"""Replay three real repairs with ANVIL checkpoints and a competent saved-patch baseline.

Requires the full Git history. No model calls; all writes are in temporary fixtures.
"""
import argparse
import contextlib
import difflib
import hashlib
import io
import json
import platform
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

from session_recovery_demo import workbench

CASES = [
    ("mixed_keys", "2ed808f7a2facf70e343d553455fe09937e3e9a9", "codec.py"),
    ("newlines", "4139f79e6e79d6be0455119e2cae779280e58722", "cli.py"),
    ("pipeline", "9a187b7b80b1436056b7b184351e3a3ad8a5aaab", "cli.py"),
]
REPEATS = 5


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def acceptance(case, root):
    sys.path.insert(0, str(root / "src"))
    from anvil_alpha.codec import CodecError, normalize
    if case == "mixed_keys":
        for value in [{"ok": 1, 2: 3}, {2: 3, "ok": 1}, {"nested": {"ok": 1, 2: 3}}, {2: 3}]:
            try:
                normalize(value)
            except CodecError:
                pass
            else:
                raise AssertionError("Invalid keys were accepted")
        assert normalize({"b": [1, True], "a": {"x": None}}) == {"a": {"x": None}, "b": [1, True]}
        return 5
    if case == "newlines":
        from anvil_alpha.cli import _write
        for text, expected in [("hello", "hello\n"), ("hello\n", "hello\n"), ("", "\n"), ("café\n\n", "café\n\n")]:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                _write(None, text)
            assert stdout.getvalue() == expected
            path = root / "written.txt"
            _write(path, text)
            assert path.read_text() == expected
        return 8
    import os
    environment = {**os.environ, "PYTHONPATH": str(root / "src")}
    def cli(*args, input=None):
        return subprocess.run([sys.executable, "-m", "anvil_alpha.cli", *args], input=input,
                              text=True, capture_output=True, cwd=root, env=environment)
    source = '{"authority":{"allowed":false},"items":[1,2,"café"]}'
    encoded = cli("encode", "-", "-", input=source)
    assert encoded.returncode == 0, encoded.stderr
    decoded = cli("decode", "-", "-", input=encoded.stdout)
    assert decoded.returncode == 0 and json.loads(decoded.stdout) == json.loads(source)
    (root / "source.json").write_text(source)
    (root / "wire.txt").write_text(encoded.stdout)
    for args, payload in [(('verify', '-', 'wire.txt'), source), (('verify', 'source.json', '-'), encoded.stdout)]:
        checked = cli(*args, input=payload)
        assert checked.returncode == 0 and json.loads(checked.stdout)["semantic_exact"]
    checked = cli("verify", "-", "-", input="invalid")
    assert checked.returncode == 2 and "cannot use '-' for both" in checked.stderr
    checked = cli("encode", "-", input="invalid")
    assert checked.returncode != 0
    checked = cli("encode", "source.json", "output.txt")
    assert checked.returncode == 0 and (root / "output.txt").read_text() == encoded.stdout
    checked = cli("decode", "output.txt", "decoded.json")
    assert checked.returncode == 0 and json.loads((root / "decoded.json").read_text()) == json.loads(source)
    return 8


def worker(stage, arm, root, target):
    wb = workbench()  # Both arms load the same module before component timing.
    started = time.perf_counter()
    if stage == "save":
        after = (root / "candidate.txt").read_text()
        if arm == "anvil":
            class RecordedCompletion:
                def complete(self, *args, **kwargs):
                    return {"complete": True, "text": after}
            session = wb.ProposalSession(RecordedCompletion())
            proposal = session.propose({"file": str(root / target), "instruction": "Replay the recorded historical repair."})
            assert proposal["reviewable"], proposal["rejection"]
            session.save_checkpoint(proposal["proposal_id"], root, root / "draft.anvil-checkpoint.json")
        else:
            before = (root / target).read_text()
            patch = ''.join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                                fromfile="a/" + target, tofile="b/" + target))
            (root / "draft.patch").write_text(patch)
    elif stage == "recover":
        if arm == "anvil":
            session = wb.ProposalSession(wb.OfflineCompletion())
            proposal = session.load_checkpoint(root / "draft.anvil-checkpoint.json", root)
            assert proposal["model_requests"] == 0 and not proposal["applied"]
            session.export_patch(proposal["proposal_id"], root, root / "draft.patch")
        git("apply", "--check", "draft.patch", cwd=root)
    elif stage == "boundary":
        if arm == "anvil":
            try:
                wb.ProposalSession(wb.OfflineCompletion()).load_checkpoint(root / "draft.anvil-checkpoint.json", root)
            except ValueError as exc:
                assert "source changed" in str(exc)
                return {"outcome": "refused_changed_target", "new_model_requests": 0}
            raise AssertionError("Stale source accepted")
        git("apply", "--check", "draft.patch", cwd=root)
        return {"outcome": "context_patch_still_applies", "new_model_requests": 0}
    return {"component_seconds": time.perf_counter() - started, "new_model_requests": 0}


def child(stage, root, case, arm=None, target=None, check=True):
    command = [sys.executable, str(Path(__file__).resolve()), "--stage", stage, "--root", str(root), "--case", case]
    if arm:
        command += ["--arm", arm, "--target", target]
    started = time.perf_counter()
    result = subprocess.run(command, capture_output=True, text=True)
    elapsed = time.perf_counter() - started
    if check and result.returncode:
        raise RuntimeError(result.stderr)
    return result, elapsed


def compare():
    repo = Path(__file__).resolve().parent.parent
    records, baselines, boundaries = [], [], []
    with tempfile.TemporaryDirectory(prefix="anvil-maintenance-comparison-") as temporary:
        for case, commit, filename in CASES:
            target = "src/anvil_alpha/" + filename
            files = {name: git("show", commit + "^:src/anvil_alpha/" + name, cwd=repo).stdout
                     for name in ("__init__.py", "codec.py", "cli.py")}
            after = git("show", commit + ":" + target, cwd=repo).stdout
            def fixture(label):
                root = Path(temporary) / (case + "-" + label)
                package = root / "src/anvil_alpha"
                package.mkdir(parents=True)
                for name, data in files.items():
                    (package / name).write_bytes(data)
                (root / "candidate.txt").write_bytes(after)
                (root / "shop.json").write_text('{"pickup":"Friday"}\n')
                return root
            root = fixture("before")
            before_check, _ = child("acceptance", root, case, check=False)
            assert before_check.returncode != 0, "Acceptance must fail before the recorded repair"
            baselines.append({"case": case, "repair_commit": commit, "before_acceptance_passed": False,
                              "failure_stderr": before_check.stderr,
                              "before_sha256": hashlib.sha256(files[filename]).hexdigest(),
                              "candidate_sha256": hashlib.sha256(after).hexdigest()})
            for repeat in range(REPEATS):
                order = ["anvil", "git_patch"] if repeat % 2 == 0 else ["git_patch", "anvil"]
                for arm in order:
                    root = fixture(f"{repeat}-{arm}")
                    result, save_wall = child("save", root, case, arm, target)
                    save = json.loads(result.stdout)
                    assert (root / target).read_bytes() == files[filename]
                    (root / "shop.json").write_text('{"pickup":"Saturday"}\n')
                    result, recovery_wall = child("recover", root, case, arm, target)
                    recovery = json.loads(result.stdout)
                    assert (root / target).read_bytes() == files[filename]
                    assert (root / "shop.json").read_text() == '{"pickup":"Saturday"}\n'
                    git("apply", "draft.patch", cwd=root)  # Throwaway fixture only.
                    result, check_wall = child("acceptance", root, case)
                    assert (root / target).read_bytes() == after
                    assert (root / "shop.json").read_text() == '{"pickup":"Saturday"}\n'
                    records.append({"case": case, "repeat": repeat, "arm": arm, "order": order,
                                    "save_seconds": save["component_seconds"], "save_process_seconds": save_wall,
                                    "recovery_seconds": recovery["component_seconds"], "recovery_process_seconds": recovery_wall,
                                    "acceptance_process_seconds": check_wall, "checks_passed": json.loads(result.stdout)["checks_passed"],
                                    "exact_candidate_restored": True, "separate_edit_preserved": True,
                                    "new_model_requests": 0, "retries": 0})
            for arm in ["anvil", "git_patch"]:
                root = fixture("boundary-" + arm)
                child("save", root, case, arm, target)
                (root / target).write_bytes(b"# A benign target-file edit after saving\n" + files[filename])
                result, _ = child("boundary", root, case, arm, target)
                boundaries.append({"case": case, "arm": arm, **json.loads(result.stdout)})
    summary = []
    for case, _, _ in CASES:
        for arm in ["anvil", "git_patch"]:
            rows = [row for row in records if row["case"] == case and row["arm"] == arm]
            summary.append({"case": case, "arm": arm, "passed": len(rows),
                            "median_recovery_seconds": statistics.median(row["recovery_seconds"] for row in rows),
                            "median_recovery_process_seconds": statistics.median(row["recovery_process_seconds"] for row in rows)})
    return {"schema": "anvil-historical-recovery-comparison-v1", "repetitions": REPEATS,
            "python": platform.python_version(), "system": platform.system(), "machine": platform.machine(),
            "baselines": baselines, "records": records, "boundaries": boundaries, "summary": summary,
            "limits": ["historical repair replay, not newly autonomous maintenance work",
                       "same committed candidate in both arms; zero new model requests in both",
                       "local component timings, not evidence of human productivity or end-to-end model speedup",
                       "human correction time and usability not measured", "one machine; no randomized machine-state control"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--stage", choices=["save", "recover", "boundary", "acceptance"], help=argparse.SUPPRESS)
    parser.add_argument("--root", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--case", help=argparse.SUPPRESS)
    parser.add_argument("--arm", help=argparse.SUPPRESS)
    parser.add_argument("--target", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if sys.flags.optimize:
        raise RuntimeError("Run without Python -O so acceptance assertions remain active")
    result = ({"checks_passed": acceptance(args.case, args.root)} if args.stage == "acceptance"
              else worker(args.stage, args.arm, args.root, args.target) if args.stage else compare())
    data = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.receipt:
        with args.receipt.open("x", encoding="utf-8") as stream:
            stream.write(data)
    print(data, end="")


if __name__ == "__main__":
    main()
