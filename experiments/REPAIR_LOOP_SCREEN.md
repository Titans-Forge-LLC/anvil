# Repair-loop replay: fast repair failed; reasoning-enabled repair passed

September 19, 2026. Replay of the known bounded-input failure, **not a fresh task**.
No new model, training, format prompt or engine fork. This investigates whether
our fast configuration was sacrificing the reasoning needed to repair a bug.

## One bounded no-reasoning loop

One resident stock Splash 1.0 server, Qwen3.8-27B package, 128 GiB M5 Max,
32 GiB budget, 8K context, greedy generation, reasoning `none`, 4096 output cap.
Source was the pre-fix public workbench at commit
`3132cb2488d7f311dbf5c76ad8695aed1a59fbb9`. Current workbench revision handling
was used; no source file was changed by the experiment.

Initial order replacement/edits; revision order edits/replacement. Both initial
attempts failed the same reviewed regression. Each received the same failure
description: a 16,385-character line including its newline must not swallow the
following valid JSON request. Feedback did not supply a code solution. Both
formats got at most one revision. Every candidate was reviewed before execution.

| Per-format loop | Atomic edits | Whole function |
| --- | ---: | ---: |
| Initial request | 3.308 s | 5.049 s |
| Initial behavioral check | 0.004 s | 0.007 s |
| Revision request | 3.074 s | 5.057 s |
| Revision behavioral check | 0.003 s | Not executed: unchanged |
| Total measured machine work | 6.389 s | 10.113 s |
| Completion tokens, both attempts | 587 | 1,286 |
| Job completed | **No** | **No** |

The edit revision changed the loop's appearance but retained the defect. The
whole-function revision repeated its previous code; the no-op guard rejected it.
Stop after the frozen limit. Neither is a cheaper completed job.

Whole trial including startup/shutdown and review pauses: 75.928 s. Startup:
6.013 s. Shared review pauses: 36.948 s and 16.229 s. These include assistant/tool
coordination, not human labor estimates or separately allocated per-arm time.

## Separate intervention: allow reasoning for the repair

The adapter had explicitly disabled thinking. Inspection of the installed server
confirmed that non-`none` reasoning settings enable thinking when the model's chat
template supports it. Register a separate diagnostic: same initial failed
proposals, feedback, model, format prompts and output cap, with effort `low`.
New server; order replacement/edits. One request per format, no further retry.
This does not erase or extend the first experiment's revision allowance.

| Reasoning-enabled repair only | Atomic edits | Whole function |
| --- | ---: | ---: |
| Request plus host checks | 11.463 s | 36.502 s |
| Behavioral verification | 0.004 s | 0.004 s |
| Completion tokens reported by server | 1,049 | 3,618 |
| Same regression result | **Pass** | **Pass** |
| Manual code correction | None | None |

Completion counts include reasoning, not just visible code; reasoning text is not
published. Both repairs check whether the oversized initial chunk already has its
newline before draining. The whole-function proposal also inserted blank lines
and retained a redundant check; correctness did not require byte-identical outputs.

Trial total including startup/shutdown and review: 83.711 s. Startup: 6.018 s;
shared review pause: 29.488 s. **Both experiments together consumed 159.640 s**,
including failures and review pauses. Investigation, test preparation, software
changes, documentation and CI are additional. The existing shipped fix was not
replaced by these replay candidates.

The successful repair-only pair has a roughly 3.18x measured-time ratio favoring
edits. It is not total task cost, independent cold-job latency, a matched
reasoning-budget result, or evidence of superiority over a competing engine.
One known task, different request order, shared caches and an adaptive intervention
prevent a general conclusion. Do not combine selected numbers from separate runs
and present them as a continuously measured successful job.

## Product decision

Keep `none` as the default. Expose an explicit Splash reasoning setting, including
a per-request override so a source-bound revision can ask for more reasoning
without losing its parent. No automatic escalation, retries, code application or
test execution. The live diagnostic used the client-level `low` setting; the
per-request override and revision binding are additionally covered by HTTP-fixture
tests, not claimed as a separate live qualification.

The next controlled comparison should freeze a policy of a cheap first attempt
followed by at most one reasoning-enabled repair, versus reasoning enabled from
the start, on fresh tasks. Count every attempt and review step. This result gives
a reason to test that policy, not to declare it qualified already.

Model snapshot: `9d27070b71f7142c6b6025f03ac011d70a73cb48`.
Raw proposals, exact-batch review approvals, test logs and trial receipts remain
private. No credentials, private user payloads or machine-specific paths appear here.

## Follow-up: two fresh maintenance tasks

Two developer-authored requests against commit
`31fa8bfc2b258072ae53f180ac6efa2d22406bda`, frozen before model generation:
configurable edit-count validation and consistent invalid-Unicode rejection.
Both operated on the existing edit parser, independently from the same snapshot.
These are new tasks for this investigation, not independent customer workloads.

Both policies used atomic edits, identical requirements, 4096 completion cap,
the same stock server/model/hardware above, and identical acceptance checks.
Fast-first used `none` initially; deliberate used `low`. Each allowed at most
one `low` repair after failure. Task order was edit limit then Unicode; policy
order reversed between tasks. All four proposals were reviewed before execution.

| Task, request plus verification | Fast-first | Reasoning from start |
| --- | ---: | ---: |
| Edit-count limit | 2.900 s | 9.310 s |
| Unicode rejection | 3.563 s | 30.533 s |
| Total measured machine work | **6.463 s** | **39.843 s** |
| Completion tokens including reasoning | 637 | 4,213 |
| Initial passes | 2/2 | 2/2 |
| Repairs needed | 0 | 0 |

Checks included requested behavior plus single-edit behavior, atomic swaps,
duplicate keys, overlapping spans, ambiguous matches and unchanged edits.
Both policies completed the scoped acceptance tests without manual correction.
The fast Unicode candidate checked reconstructed output; the deliberate one
checked source immediately. Both passed. The latter was chosen for clearer
entry validation and carried into the workbench after review; configurable
edit counts remain experimental rather than adding an unused public option.

Total shared trial: **90.997 s**, including **10.040 s** startup, **34.428 s**
review/coordination pauses, requests, checks and shutdown. Engineering, test
preparation and CI are additional. No startup or shared review time is silently
allocated to one policy. Raw request totals were 6.454 s and 39.834 s; verification
totals were 0.009 s and 0.009 s respectively.

The roughly 6.16x machine-time ratio is only for these two small same-function
tasks. Shared server caches, small sample, developer-authored requirements and
non-independent task types limit inference. **No failure occurred, so the repair
branch was not exercised and the escalation policy is not qualified.** This is
not an ANVIL-versus-Splash comparison: both policies used Splash.

Decision: retain the fast default and explicit reasoning option. Do not add an
automatic scheduler or claim general speedups. Next evidence should come from
ordinary maintenance jobs that need doing, including failures when they occur,
not from increasingly contrived tasks designed to trigger the repair branch.

## Ordinary maintenance follow-through: larger modules

The next useful job was removing the full-file 32 KiB obstacle when editing a
small named function. One fast atomic-edit proposal took 5.490 s on the same
stock model. It failed the frozen behavior check: it increased the initial read
limit but left the post-generation reread at the old limit, so a larger unchanged
file was treated as changed. It also omitted the whole-file input restriction.
No second model attempt was made. The host implementation was corrected manually,
with both reads bounded consistently and separate module/function limits.

The failed check took 0.009 s; whole trial including startup, review and shutdown
was 37.649 s, of which startup was 6.018 s. Manual correction and the subsequent
regression suite are additional work, not credited as autonomous model success.
The resulting product change accepts modules up to 1 MiB in named-function mode,
preserves 32 KiB function and whole-file limits, and keeps source hashes/revisions.
This is a delivered usability improvement, not a speed comparison. It reinforces
why complete-job outcomes must include host review and correction.

## Helper-context trial: missing-executable receipts

September 20, 2026. A real usability defect in `create_test_receipt.py`: a
missing Node/Git executable could crash receipt creation. One fast atomic-edit
request per arm, same task and 4096 completion cap, stock Splash/Qwen3.8-27B.
Order: no context, then the three explicit command/version helpers (691 bytes).
Both requests restricted editing to `main`. No retries or rescoring.

| Result | Without helpers | With helpers |
| --- | ---: | ---: |
| Request and host validation | 4.064 s | 28.591 s |
| Prompt tokens | 1,051 | 1,265 |
| Completion tokens | 335 | 4,096 |
| Outcome | Rejected: extra function | Incomplete: output limit |

Neither candidate reached behavioral execution; the harness recorded rejection
in under 0.001 seconds each. Neither completed the job. Shared whole trial was
61.917 s, including 10.015 s startup and 19.026 s review/coordination pause.
Source remained unchanged. No evidence here that adding context improves results.

Task decomposition was also a limitation: the natural correction belongs in
the three helpers, not `main`. The manual product fix catches FileNotFoundError
at those boundaries, retaining successful behavior and propagating unexpected
exceptions. That manual correction and its regression checks are additional work,
not credited to the model. One ordered task does not establish that helper
context is generally harmful. Keep it opt-in; select the right edit scope before
adding more context or output budget. No automatic scope expansion was added.

## Correct-scope follow-through: bounded receipt waits

The next maintenance job put timeouts in the three existing command helpers,
instead of forcing a change through `main`. Three separate proposals, no context,
reasoning `none`, whole-function format, 1024 completion cap each. Same stock
Splash/Qwen3.8-27B model; baseline `cda44be7e6247f57b00e56a98e45985ab3862e1e`.

| Helper | Request time | Completion tokens | Mocked behavior checks |
| --- | ---: | ---: | --- |
| command_result | 1.338 s | 138 | Pass |
| git_commit | 0.847 s | 87 | Pass |
| node_version | 0.773 s | 83 | Pass |

All three passed first try, with no code corrections. Request total 2.957 s;
mocked-check total 0.005 s. Whole trial 31.727 s, including 10.035 s startup and
18.479 s review/coordination pause. No retries. Integration, regression tests,
documentation and CI are additional work. The host manually integrated the exact
reviewed function replacements; this was not autonomous application.

Checks covered requested timeout kwargs, TimeoutExpired, missing executables,
successful/nonzero exits and propagation of unexpected exceptions. They mock
subprocess execution; they do not demonstrate waiting for a real hung process.
Conformance subprocesses request 300 seconds each; optional metadata requests 10.
These are subprocess timeouts, not a guaranteed whole-job deadline or process-tree
sandbox. Descendant-process handling and process creation have separate limits.

This is successful delivery of a small scoped job, not a controlled causal test
of scoping. Task, output format and budget differ from the preceding failure.
Do not divide those runs' timings and claim a speedup. No new planner, automatic
scope expansion or multi-function editing engine was needed for this job.
