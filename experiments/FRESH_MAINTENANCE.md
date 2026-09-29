# Fresh maintenance: both proposal formats needed correction

September 19, 2026. One real workbench bug, discovered after the earlier
[edit-span screen](EDIT_SPAN_SCREEN.md), not another replay of its three tasks.

## Task and frozen acceptance

Function selection mapped Python AST line numbers using `str.splitlines()`.
That method also splits Unicode separators, NEL, vertical tab and form feed
inside comments/strings, unlike Python's physical LF/CRLF/CR lines. This can
select the wrong source slice. The boundary reconstruction also omitted bare CR.

Before model inference, a regression test reproduced 15 failures: five non-Python
separators in comments crossed with LF, CRLF and CR. The requirement was exact
function selection, correct replacement, unchanged surrounding bytes and no disk
writes. The model received the defect description and function, not the tests.

Same unmodified Splash 1.0 / Qwen3.8-27B package, one shared server, 32 GiB budget,
8K context, temperature zero, reasoning disabled, 4096 output-token limit.
Order: edit, then whole-function replacement. No engine hook or model retry.

## Results, including failures

| One request per format | Exact edit span | Whole-function replacement |
| --- | ---: | ---: |
| Completed and structurally reviewable | Yes | Yes |
| Output tokens | 179 | 1,594 |
| Proposal elapsed, including host checks | 3.272 s | 11.635 s |
| Regression subcases passing | 0/15 | 10/15 |
| Accepted without repair | No | No |

The edit proposed a variable-width regex lookbehind that Python rejects at
runtime, and omitted the other requested boundary changes. The replacement
split CRLF twice, failing all five CRLF cases. Both were rejected on review;
subsequent execution of only the reviewed candidate code confirmed those errors.
Structural validity is not behavioral correctness.

Server startup took 6.025 s. The combined trial, including startup, proposals and
shutdown, took 21.145 s. A recorded joint assistant review wall interval was
14 s; this is not human labor or a matched per-format review benchmark. Candidate
verification was run twice (the second to retain a full diagnostic receipt), with
the same failures. No structural fallback fired because both formats passed the
structural gate. **One direct, assistant-authored repair was still required.**
Proposal latency alone therefore cannot be called time to a completed job.
Download and environment setup were already done. Documentation, investigation,
manual repair, regression work and hosted CI are not included in the 21.145 s;
this is explicitly not a complete task-cost measurement or a speedup claim.

## Shipped repair and decision

Match only CRLF, CR and LF when mapping physical lines; preserve the bare-CR
boundary in both proposal modes. Keep source bytes outside the selection intact.
The repaired code passed all 15 regression cases and the 49-method local suite.
The existing edit-boundary rejection test also covers LF, CRLF and bare CR.

Keep edit spans opt-in and whole-function replacement the default. Neither model
output was installed. The workbench still never applies or executes a proposal.
There is no evidence here for changing the model, adding a routing architecture,
or claiming completed-job savings. The immediate gain is a real correctness fix
and an honest negative example that qualifies the earlier positive screen.

## Provenance and reproduction

Model snapshot: `9d27070b71f7142c6b6025f03ac011d70a73cb48`.
Input workbench SHA-256:
`3a24de1181a226542289578974f6a690b42dc8b65efb17c76bae7c0b02136b11`.
Raw proposals, server logs and diagnostic receipts remain private; this page
contains no user payloads, credentials or machine-specific paths.

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_workbench.py'
PYTHONPATH=src python -m unittest discover -s tests -p 'test_edit_proposals.py'
```

These reproduce the shipped regression checks, not the exact timed model trial.

## September 29: fresh JSON-root verifier repair

A new, existing public CLI defect: `verify` assumed both JSON roots were objects
and crashed on arrays and scalars, despite the codec supporting those roots.
Frozen checks reproduced the failure before inference. Both arms received the
same targeted-edit prompt, source, parser, sandbox checks and one-correction cap.
The direct arm used ordinary explicit checkpoint handling; ANVIL used its
retained proposal session, checked candidate, checkpoint restore and export.

| Result | Direct control | ANVIL session |
| --- | ---: | ---: |
| Model requests | 1 | 1 |
| Corrections needed | 0 | 0 |
| Frozen check methods passing | 5/5 | 5/5 |
| Recorded arm elapsed | 6.742 s | 5.615 s |
| Later offline delivery correction | 0.010 s | 0.008 s |

Both produced identical candidate bytes. The model was the resident
`qwen3.8-flash-next`, temperature zero and reasoning disabled. Shared model-access
setup took 0.615 s; the original campaign took 13.140 s. These are machine
intervals, not human task costs. Direct ran first; engine cache state was not
controlled. **No speedup or coding-quality advantage is established.**

The trial harness appended a newline to both convenience candidate files and
initially exported a generic-header control diff. Exact candidate bytes remained
intact in the checked proposals and checkpoint JSON. A subsequent offline export
correction preserved the original receipts, generated project-relative patches
for both arms and verified that each applied to the exact checked candidate.
No model retry was used. This later work and human test authoring/review are not
included in the original arm timings.

The reviewed candidate is included in this development change, with permanent
CLI regressions. Verification now treats non-object authority as absent on each
side independently and preserves semantic mismatch failures and object checks.
The workbench itself did not apply the patch or alter live source. The trial
exercises fresh proposal/check/restore/export, **not** the correction branch or
independent customer acceptance. It supports workflow usability on one task,
not an economic advantage over ordinary competent tooling.

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_codec.py'
```

This reproduces the added regression tests, not the timed model comparison.
