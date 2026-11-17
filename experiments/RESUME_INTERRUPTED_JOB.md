# Resume an interrupted local Python job

Use this workflow to hand off a draft from a maintainer or any coding tool. It
supports one changed top-level Python function per capsule and up to four
named helpers in the same file. Keep the capsules and navigation notes private.
Use locally excluded paths for private draft files and capsules. This also
keeps them out of the compact Git snapshot, which refuses large untracked
files it cannot fingerprint.

## Before pausing

In the Git worktree root, keep the current base in `module.py` and put the full
draft file in `candidate.py`. Save the task in `task.txt`. Compute the base hash
when selecting the source for the draft and use that recorded value at capture.

```sh
python -c "import hashlib,pathlib; print(hashlib.sha256(pathlib.Path('module.py').read_bytes()).hexdigest())"
anvil-capture --project-root . --source module.py --candidate candidate.py \
  --symbol target --context-symbol helper --intent-file task.txt \
  --source-sha256 BASE_SHA256 --output draft.json
```

Add `--check-failed` if the candidate failed a check. This preserves the draft
and blocks patch export until an explicitly run current check passes. For
offline repair, use the existing workbench's resume or resolve command with the
current intent and a locally registered check plan. Workbench checks require
macOS. A check run explicitly by a maintainer through Git remains available on
other platforms.

Optionally save the exact failing check and a short description of a rejected
approach. The navigation file lives outside the repository so saving it does
not itself change the recorded Git state.

```sh
anvil-predraft capture --project-root . --task-file task.txt \
  --output ../private-handoff.json --failed-check 'python check.py' \
  --dead-end 'The first draft failed the missing-value case'
```

## On return

```sh
anvil-predraft inspect --project-root . --handoff ../private-handoff.json --compact
anvil-job --project-root . --intent-file task.txt --export-patch resume.patch draft.json
git apply --check resume.patch
```

The compact view displays four lines with freshness, dirty file locations, the
recorded command and the recorded dead end. Treat those hints as private history.
Choose current checks yourself. Review the patch before applying it and run
those checks afterward. A changed selected function, declared helper, module
environment or task requires review before reuse. Capsules from older versions
remain readable. Old checkpoint readers refuse the new quarantine format.
