# Changelog

## Experimental workbench preview — September 19, 2026

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
