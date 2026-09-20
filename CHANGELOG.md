# Changelog

- Test-receipt tool now emits a complete FAIL receipt when a conformance
  executable is missing, and null for unavailable Git/Node metadata. Exception
  messages and filesystem paths are not included; unexpected errors propagate.

- Workbench: opt-in `context_symbols` supplies up to four read-only helper
  functions from the same file, capped at 8 KiB. Revisions inherit context;
  edits remain restricted to the selected target. No default prompt change.

- Named-function workbench edits now support modules up to 1 MiB, with 32 KiB
  selection/replacement limits and unchanged whole-file limits. Full-module
  source binding and stale-revision checks remain in force.

- Workbench: reject invalid Unicode in edit sources/envelopes/scalars with
  consistent ValueError; preserve valid emoji and existing atomic edit checks.
- Publish two fresh maintenance-policy results, including shared costs and the
  unexercised repair-branch limitation; keep fast defaults unchanged.

## Experimental workbench preview — September 19, 2026

- Added explicit Splash reasoning defaults and per-request/revision overrides;
  keep none as default, preserve source bindings, and reject unsupported MLX CLI
  settings. Publish failed bounded repairs and a separate successful reasoning-on
  intervention, counting reported completion tokens and shared review costs.

- Bound CLI input reads and drain oversized requests without losing the next
  valid request. Preserve the shared model boundary failure and counted direct
  repair from the larger fixed-format maintenance experiment.

- Reject unchanged proposals without consuming revision slots, while preserving
  legitimate parent reversions. Shipped the reviewed model-generated fix after
  a fresh fixed-format comparison; retained startup, review and timing limits.

- Added opt-in atomic multi-edit proposals with unique snapshot-bound anchors and
  all-or-nothing overlap rejection. Published failed initial attempts and one
  successful adaptive replay; no change to the default format.
- Applied the reviewed local-model input-token accounting change to the Splash
  adapter, with strict validation and unknown counts preserved as null.

- Fixed Python physical-line source selection and bare-CR proposal boundaries.
  A fresh maintenance trial found both model formats needed correction; published
  those failures rather than treating fewer output tokens as a completed-job win.

- Added opt-in exact old/new edit spans inside a selected function, preserving
  source bindings and proposal-only revisions. Reject malformed/ambiguous edits.
- Published a live same-model comparison: 6/6 requested transformations in each
  format, lower aggregate tokens/time with spans, and the short-task regression.

- Tested a source-draft hook inside an isolated Splash engine. Published mixed
  economics, corrupted-draft fallback and output-equivalence observations;
  retain the experiment without changing the public runtime default.

- Ran Splash 1.0 with its supported 27B package: 12 completed requests, six
  identical direct/ANVIL pairs, and three exact requested AST transformations.
  Report startup and warm-cache effects separately; no combined speedup claim.

- Added a loopback Splash chat-completion adapter for source-bound proposals and
  revisions. No MLX dependency on the client path; engine counters remain unknown.
- Verified HTTP contract and failure boundaries with a local fixture. Live Splash
  performance and engine-level ANVIL source drafting remain unqualified.

- Added opt-in source drafting for first edits, with target verification and
  ordinary fallback. Published a reproducible three-request comparison and
  metadata-only receipt; no general coding-speed or task-quality claim.

- Added bounded, source-hash-bound in-memory proposal revisions via `revise` IDs.
  Revisions preserve file/symbol scope and never apply changes automatically.
- Supply code verbatim instead of JSON-escaping it in prompts; document both the
  failed and corrected newline-maintenance trials.
- Reviewed and applied the corrected CLI newline-handling proposal with tests.

- Added named top-level Python function editing, preserving surrounding code
  and rejecting wrong-name, extra-statement and invalid-syntax replacements.
- Used the workbench to propose the codec mixed-key validation repair; reviewed
  and applied it with regression coverage. Valid-input wire encoding is unchanged.

- Added a resident, local-only single-file editing proposal loop with optional MLX.
- Retain exact responses and causal prefixes; target-check the previous answer
  as a draft, rolling back and resuming ordinary generation on mismatch.
- Include source-bound review diffs, timings, an ordinary-mode comparison,
  a small editing exercise, and dependency-free correctness tests.
- No automatic patch application, code execution, private data or weights.
- Keep AVP1 and the existing beta tag unchanged; document the older model adapter
  and the narrowly measured prototype result separately from this new preview.

## 0.2.0-beta.1 — Limited public beta

- Set a target beta window through approximately September 11, 2026; full
  release remains evidence-gated.

- Reframed the first release as a limited, source-only public beta.
- Added a fail-closed release boundary with explicit allowlist and
  private-material denylist enforcement.
- Added a privacy-bounded independent reproduction receipt.
- Added beta testing, evidence, release, and rollback guidance.
- Added a blinded reasoning-signature experiment whose oracle validates only
  the instrumentation pipeline.
- Added `anvil` as the primary command while retaining `anvil-alpha` as a
  compatibility alias during the beta.
- Preserved AVP1 as the synthetic, dependency-free public reference profile.

The beta does not include the private optimized codec, private corpora, trained
models, live Forge integration, hosted services, or production authority.
