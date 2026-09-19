# Changelog

## Experimental workbench preview — September 19, 2026

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
