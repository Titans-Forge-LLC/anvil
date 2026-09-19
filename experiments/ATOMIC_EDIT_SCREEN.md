# Atomic edits: a faster successful replay, with failed development attempts

Follow-up: the fixed format subsequently passed a fresh task without tuning;
see [the fresh no-op task](#fresh-task-with-the-shipped-format-held-fixed) below.

September 19, 2026. Goal: stop regenerating unchanged code when a task touches
several locations in one function. No engine fork, new model or automatic execution.
Whole-function replacement remains the default.

## A useful task, not synthetic expensive work

Add input-token accounting to `SplashCompletion.complete`: consume reported
`usage.prompt_tokens`, preserve missing/null as unknown, reject any value other
than an exact nonnegative integer (including bool), return `input_tokens`, and
leave existing behavior/output counts unchanged. The method was extracted and
dedented verbatim because the current selection API accepts top-level functions.
The behavioral test was written before dispatch and not shown to the model.

Both formats received the same original source and instruction. Stock Splash 1.0,
supported Qwen3.8-27B package, 128 GiB M5 Max, 32 GiB engine budget, 8K context,
temperature zero, reasoning disabled. Format instructions differ. No engine hook.

## Preserve the first failure

Initial order: replacement, edits, edits, replacement. Output cap 4096.

| Format | Request + host checks | Output tokens | Outcome |
| --- | ---: | ---: | --- |
| Whole function | 6.182 s | 814 | Behavioral check passed |
| Atomic edits | 27.092 s | 4096 | Repetition; truncated, rejected |
| Atomic edits | 27.767 s | 4096 | Repetition; truncated, rejected |
| Whole function | 5.695 s | 814 | Behavioral check passed |

The two repeats are not separate unseen tasks. No retry or execution of truncated
responses. Initial trial wall time including startup/shutdown: 77.057 s;
startup 10.022 s. The proposed format initially **lost badly**.

## One registered correction, then stop

Before further inference, record one task-independent JSON envelope example in
the format prompt and lower both arms to a 1024 output cap. No solution hints,
test details, source change, model change or instruction change. New shared server;
order edits then replacement. This is an **adaptive development replay**, not an
independent validation of the corrected prompt or proof of what caused the change.

| Corrected replay | Atomic edits | Whole function |
| --- | ---: | ---: |
| Output tokens | 213 | 814 |
| Request + host checks | 2.743 s | 6.050 s |
| Behavioral verification | 0.508 s | 0.513 s |
| Combined measured request + verification | 3.251 s | 6.563 s |
| Behavioral result | Pass | Pass |
| Further repair or retry | None | None |

The corrected edit used 73.8% fewer output tokens and about 50.5% less measured
request-plus-verification time on this one task. Both candidates were manually
reviewed before running their checks. Verification used the same local HTTP
fixture, including its lifecycle, not a model-generated test. The chosen edit
was applied without correction; the full 53-method local suite then passed.

## Costs and limits

Corrected trial wall time including startup/shutdown: 15.037 s (startup 6.018 s).
Both model trials together cost 92.094 s, including the failed attempts. Joint
assistant review of the corrected pair had an 18-second recorded wall interval;
it is not per-arm human labor. Earlier review and implementation time were not
fully instrumented. Full-suite testing took 4.640 s; documentation and hosted CI
are additional. Therefore 3.251 s is **not complete developer-job cost**.

There was no structural fallback invocation, because the protocol specifies no
automatic retries. The two initial truncated attempts are failures, not omitted
requests. No successful outputs were silently repaired. The workbench never
executes candidates; this experiment executed only manually reviewed definitions.

The example increases prompt size; smaller output does not mean smaller input.
No cold end-to-end win, general reliability improvement, distribution-equivalent
decoding, training gain or competitor superiority is claimed. Splash is the
underlying engine in both arms, not a separately measured competing product.

## Product decision and provenance

Expose atomic edits as opt-in, retain strict snapshot/overlap rejection, and keep
the working full-function fallback available to the caller. Do not select a
default from this single adaptive task. This tests one plausible workflow gain,
not an architecture replacement. Next evidence should come from fresh jobs,
without further tuning this task.

Source method SHA-256:
`ee5ee52ce7bbd8aaf7d8a945ab05f4fe45834d64ffe72a90de978f5933ddb611`.
Model snapshot: `9d27070b71f7142c6b6025f03ac011d70a73cb48`.
Raw proposals, source fixture and logs are retained privately. No credentials,
private payloads or machine paths are included here.

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_edit_proposals.py'
PYTHONPATH=src python -m unittest discover -s tests -p 'test_splash_adapter.py'
```

These reproduce product behavior checks, not the exact historical model timing.

## Fresh task with the shipped format held fixed

A subsequent task used the exact shipped format prompts, without tuning: reject
unchanged proposals after reconstruction, comparing against the current revision
source rather than the original disk file. Deliberately reverting a parent must
remain valid; cancelling atomic edits must be rejected as unchanged. This prevents
empty review work and wasted revision slots. A failing regression was frozen
before dispatch and withheld from the model.

Same engine/model/hardware profile as above; 4096-token cap for both formats.
Order: edits, replacement, replacement, edits. This is **one fresh task repeated
twice**, not four independent tasks. All four proposals passed the same behavioral
check after manual review. No retries, fallback, repairs or prompt adjustments.

| Across two requests each | Atomic edits | Whole function |
| --- | ---: | ---: |
| Input tokens | 4,174 | 3,936 |
| Output tokens | 236 | 3,652 |
| Request + host checks | 4.654 s | 25.941 s |
| Behavioral checks | 0.006 s | 0.005 s |
| Combined measured time | 4.660 s | 25.946 s |
| Requested behavior | 2/2 pass | 2/2 pass |

About 82.0% less measured request/check time (5.57x ratio) on this task.
The output reduction is much greater than the input-plus-output reduction;
the edit instruction costs 119 additional input tokens per request. Input tokens
are counted even when a server might cache them; token counts are not FLOPs.

Individual request times in order were 3.426, 13.929, 12.012 and 1.228 seconds.
The first edit incurred cold-server/prefix costs. Shared cache and repetition
affect timing, so neither the warm pair nor the aggregate establishes a broad
coding-speed claim. This does not compare competing engines.

Initial Windows CI exposed newline translation in the new regression fixture:
text-mode writing produced CRLF while the mocked response used LF. The fixture
now writes explicit UTF-8 bytes, matching the original Mac experiment. No product
or model output was changed for this correction; failed CI remains in PR history.

Total trial startup/generation/shutdown: 36.876 s, including 6.015 s startup.
Joint assistant review wall interval: approximately 12 seconds; no per-arm human
review cost was measured. The selected edit was applied unchanged and the complete
54-method local suite passed in 4.644 s. Investigation, test writing, implementation,
documentation and CI remain outside the quoted request/check timings. This is not
complete developer-job cost. Raw proposals/logs remain private.

Decision: retain the opt-in format and ship the useful no-op guard. The fixed
prompt generalized to this fresh task; one task does not establish general
reliability or justify changing the default. No engine change or model training.
