# Changelog

## 0.2.0-beta.1 — Unreleased

- Reframed the first release as a limited, source-only public beta.
- Added a fail-closed 56-file release boundary with explicit allowlist and
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
