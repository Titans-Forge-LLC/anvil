# Source drafts inside Splash: working prototype, no promotion

September 19, 2026. This follows the [live HTTP integration](SPLASH_LIVE_SMOKE.md).
An isolated native-engine modification actually replaced DFlash proposals with
ANVIL source tokens. It was not merely an HTTP wrapper. The public adapter and
installed Splash runtime remain unchanged.

**Decision:** retain the experimental hook, but do not enable it by default.
Correctness observations were encouraging; the aggregate economic gain was not.
[Metadata-only receipts](splash_source_engine_screen.json) preserve both screens
and an initial launcher failure. This page reports a local prototype, not a
reproducible public engine release; the engine fork/build harness is not shipped.

## Minimal intervention

Upstream Splash revision `f58d36ddb046726adc8937ab67d07bdde015c0d6`; same supported
27B package, hardware, 32 GiB allocation ceiling and 8K context as the live smoke.
Baseline and candidate were compiled with identical compiler/SDK settings and
the same official, unchanged Metal library. No new GPU kernels were introduced.

The hook loads a small immutable table from exact prompt token sequences to
source token sequences. Only greedy, unconstrained, text-only, width-one requests
are eligible. It checks the target-selected anchor against the corresponding
source token, then supplies the next seven source tokens instead of computing
the learned draft. Splash still verifies them and commits accepted target KV,
recurrent state and drafter context through its existing code. After a mismatch
or short tail, DFlash resumes. Source text cannot approve its own output.

This is an experimental process-local interface, not a production request API.
Concurrent scheduling, suspension/resume, stochastic sampling, constrained
generation and durable cache restoration are not qualified by these results.

## Observations

The same three public edits used by the earlier source-draft screen were fixed
before generation. ABBA server order was baseline, source, source, baseline.
Servers were restarted between arms. A separately registered follow-up repeated
each request within the server to measure the intended warm-session use case.

| Six comparable requests | DFlash baseline | Source-first hook |
| --- | ---: | ---: |
| Initial cold screen | 6.432 s | 6.541 s |
| Follow-up first pass | 6.490 s | 6.532 s |
| Follow-up warm pass | 4.891 s | 4.848 s |

Source binding construction/tokenization took 0.039 s in the initial screen and
0.024 s in the follow-up. These costs are additional to request time. Combining
first and warm request passes in the follow-up yields 11.381 s baseline versus
11.380 s candidate **before** adding construction: effectively no gain.

Warm task averages, two observations per arm:

| Task | Baseline | Candidate |
| --- | ---: | ---: |
| Late mapping-comprehension edit | 1.204 s | 1.159 s |
| Short encoding edit | 0.228 s | 0.217 s |
| Early docstring insertion | 1.013 s | 1.048 s |

Startup/teardown are not hidden: complete server lifetimes are in the receipt.
The initial campaign, including the adversarial arm, took 50.411 s. The warm
campaign took 49.266 s including four server starts/stops and construction.
Startup variability must not be attributed to drafting: one warm-campaign
baseline startup was about 1.9 s longer than the others. Downloads, compilation
and human review are outside these campaign totals. They are not job-cost claims.

There were 43 recorded responses across both completed campaigns: 41 completed
and two intentional one-token truncations. No output hash disagreed with its
corresponding baseline. Every completed proposal was structurally reviewable;
no generated code was applied or executed. This is a small correctness screen,
not proof of unrestricted equivalence or broad coding quality.

The normal source runs accepted 128, 14 and 10 source-draft tokens respectively
across 19, 2 and 2 source blocks. Counts exclude target-selected anchors. Thus
the hook demonstrably ran; identical answers were not caused by a disabled hook.

## Adversarial checks and preserved failures

- Corrupting token 10 forced rejection after an accepted block. Each task recorded
  two source blocks and eight accepted proposal tokens, then completed with the
  baseline answer through DFlash fallback.
- A changed prompt had no matching source binding and used the ordinary path.
- A one-token output budget emitted no source block and remained incomplete,
  rather than presenting truncated code as reviewable.
- Pure C++ checks covered anchor mismatch, short/empty source, out-of-range
  offset, permanent disable after rejection and missing binding-file rejection.
- The first runner failed before inference: direct server flags require numeric
  sizes, unlike launcher shorthand. That failed receipt is retained, not scored
  as a model failure. The corrected runner did not change decoding policy.

## Architectural takeaway

An exact source draft can coexist with the existing verifier and safely return
to the learned drafter in this tested setting. But skipping draft generation
does not skip target verification, and this hook keeps the same eight-row
verification shape. High source acceptance alone therefore does not imply a
large speedup. Do not multiply the older MLX gain by Splash's upstream claims.

The next product experiment should reduce required output: source-hash-bound
edit spans that preserve unchanged text in the host, compared against today's
whole-function proposal. Count successful jobs, reconstruction, review and
fallback cost. Keep this engine hook as a research foundation; do not spend
another round tuning milliseconds on these same three functions.
