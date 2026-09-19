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
