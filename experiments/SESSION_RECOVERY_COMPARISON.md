# Three interrupted repairs: checkpoint versus saved Git patch

## Result

On October 9, 2026, both arms restored the exact committed candidate and kept
a separate-file edit in **15 of 15 recovery trials per arm**. Both used **zero
new model requests** and no recovery retry. This is a historical repair replay,
not three newly autonomous repairs or a human productivity study.

When a benign comment was subsequently added to the target file, ANVIL refused
all three checkpoints. Git's context patches still passed `git apply --check`
in all three cases. That is a useful distinction: ANVIL requires the exact
original file, while Git can accept a contextual patch after some other edits.
Neither outcome proves the resulting code is correct in an arbitrary project.

## Repairs and acceptance checks

| Historical repair | Committed repair | Checks after recovery |
|---|---|---|
| Reject mixed JSON mapping keys with the intended codec error | `2ed808f7a2facf70e343d553455fe09937e3e9a9` | Four invalid-key arrangements and a valid nested value |
| Avoid appending an extra newline to CLI output | `4139f79e6e79d6be0455119e2cae779280e58722` | Four text cases each on stdout and a file |
| Support stdin/stdout pipelines without ambiguous double-stdin verification | `9a187b7b80b1436056b7b184351e3a3ad8a5aaab` | Stream round trip, each verify input, ambiguous stdin rejection, malformed input, file encode/decode |

The same checks failed on each historical pre-repair file and passed after each
recovered candidate. The original failures are retained in the receipt; no
failed run is relabeled as a new fix.

## Matched conditions

Each trial used fresh throwaway fixtures from the repair's parent commit, the
same recorded final candidate, and a new subprocess for recovery. Five repeats
per repair alternated ANVIL-first/Git-first order. Both arms loaded the same
workbench module before component timing and ran `git apply --check` before
applying only to the throwaway fixture. Both then ran identical acceptance
checks in another process. An unrelated `shop.json` edit was made between save
and recovery and verified afterward. No model server was called.

Measured on one Darwin arm64 machine, Python 3.12.14:

| Repair | ANVIL median recovery/check | Saved Git patch median recovery/check |
|---|---:|---:|
| Mixed keys | 11.24 ms | 9.97 ms |
| Newlines | 10.45 ms | 9.57 ms |
| Pipelines | 10.35 ms | 10.03 ms |

These are component measurements including the Git applicability check. They
exclude interpreter/module startup, original generation, human review and the
later acceptance subprocess. Full recovery process medians were about 42–45 ms.
The [machine-readable receipt](session_recovery_results_20261009.json) contains
every repetition, source/candidate hashes, failure summaries, component and
process timings, and changed-target outcomes. An additional Python 3.9.6 local
replay also passed; the table above uses the 3.12.14 run.

There is **no demonstrated speed advantage** here. Differences this small on
one machine are not a reliable productivity result. A saved Git patch is a
competent baseline; retaining a draft is useful with either method. Human
correction time, review quality and ease of use were not measured.

## Reproduce

Use a full Git clone of this repository, with the historical commits available:

```sh
python3 experiments/recovery_comparison.py --receipt ../anvil-recovery-results.json
```

The receipt destination must be new. Python 3.10+ and Git are sufficient; no
model or additional packages are needed. Do not use Python `-O`. A source ZIP
without Git history can run the [small restart demo](SESSION_RECOVERY.md), but
cannot reconstruct these historical repairs.

## Next useful evaluation

Run three fresh maintenance tasks with a real interruption and an independent
reviewer. Record completion, total elapsed time, retries, human correction
minutes and whether anyone approves stale work. Freeze the candidate and checks
for both arms and retain failures. That would test practical usefulness beyond
this offline recovery comparison.
