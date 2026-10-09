# The session ended. The draft survived.

You have an unfinished code change. You close the session. Someone changes
another file. Can you pick up the draft, check it, and keep their edit?

This small demonstration shows that workflow with ANVIL. A saved checkpoint
retains the candidate, original file hash and declared edit scope. In a fresh
process, ANVIL checks the source and restores the candidate for review without
asking a model again. Saving work does not approve it.

## Run it locally

From the root of this checkout, with Python 3.10+ and Git installed:

```sh
python3 experiments/session_recovery_demo.py
```

No Python packages, model download, account or server are required. The script
creates temporary fixtures and removes them afterward. It does not edit your
project, install anything or contact a model. Windows users can substitute
`py -3` if needed. Do not run with Python `-O`.

Expect a JSON receipt reporting:

- `save.saved: true` and `recovery.restored: true`, from separate processes.
- `recovery.new_model_requests: 0` and `recovery.applied: false`.
- `separate_file_edit_preserved: true` — pickup changed from Friday to Saturday.
- `git_apply_check_passed: true` and `behavior_checks_passed: 3`.
- `changed_target.changed_target_refused: true` after changing the target file.

The script applies the exported patch only to a **throwaway copy** to check
empty, positive and mixed-sign inputs. The reviewed source remains unchanged.
To retain the receipt, supply `--receipt` with a new filename outside the checkout.

## What this demonstrates

The candidate is a recorded empty-input repair to a tiny averaging function.
The script does not generate a new answer. A scripted separate-file edit stands
in for a colleague's change; it is not a live collaboration study. The original
film used a real local-model candidate; this reproduction uses its exact final
replacement bytes (SHA-256
`893b8a9e0dec9920ba199cef21ebfd68d6ad5cfabee1f7d4bd06f51615ccc638`).

A checkpoint is saved proposed code, not a model's internal memory. It is not
encrypted or authenticated and should be kept private. Source matching is a
point-in-time check, not a lock against another editor. Any change to the target
file, even a harmless comment, causes this checkpoint to be refused. Request a
fresh proposal in that case.

## What about simply saving a Git patch?

That works too. A saved patch can survive a restart and preserve changes in
other files without another model call. ANVIL adds declared review scope and
exact source matching to the retained candidate. That stricter check can also
create extra work when a harmless target-file edit would still allow a Git
patch to apply. Correctness still needs tests and human review in either case.

The [three-repair comparison](SESSION_RECOVERY_COMPARISON.md) records this
boundary and its limitations. It does not claim a speed or productivity gain.

## Try it on your own unfinished work

Follow [Start Here](START_HERE.md#stop-now-review-later--no-model-needed) to save
an actual proposal, quit, and load it using the offline backend. Inspect the
diff, export a patch to a new filename, run your project's checks, then decide
whether to apply it. ANVIL does not make that decision for you.
