# ANVIL Limited Public Beta Evidence Packet

Status: `UNSIGNED RELEASE CANDIDATE / PUBLICATION NOT AUTHORIZED`

This packet defines the evidence and claim boundary for the first ANVIL limited
public beta. The authoritative file inventory and per-file hashes are in
`RELEASE_MANIFEST.json`; the manifest must report `PASS` on the exact revision
selected for release.

## What ships

- The AVP1 `governed-mission-v1` reversible reference codec.
- Python and browser implementations with cross-runtime wire conformance.
- A synthetic governed-mission fixture and local command-line workflow.
- A fail-closed public-file allowlist and private-material denylist.
- A privacy-bounded receipt generator for outside reproduction.
- An optional, explicitly non-conclusive reasoning-signature experiment.

The package contains no live Forge dependency, private directive corpus,
trained model, model weight, filing document, credential, or production
integration.

## Locally verified observations

The clean-copy receipt records:

- package build and install: `PASS`;
- release verifier: `PASS`;
- deterministic manifest parity: `true`;
- semantic exactness: `true`;
- authority exactness: `true`;
- canonical JSON: `723` bytes;
- AVP1 wire: `558` bytes;
- ratio on the single shipped synthetic fixture: `1.2957x`.

The receipt SHA-256 is
`19eb9b642e37a1f5ef90f2e1df675c2f63e0fb4688140d3448996bd81955c73f`.
The receipt preserves an initial offline-build failure caused by a missing wheel
build helper and records the successful bounded resolution.

On the current candidate, the Python conformance suite reports `9` passing
tests and the standalone browser codec suite passes. These counts are
diagnostic and must be regenerated for the exact release revision.

The `0.2.0b1` candidate also built into a wheel and installed offline into a
fresh virtual environment, where the primary `anvil` command and module import
both succeeded. The wheel is not included in the source-only beta; see
`BETA_CANDIDATE_BUILD_RECEIPT_V0_1.json`.

## Claims permitted by this packet

- AVP1 is a deterministic, reversible public reference profile for the shipped
  synthetic governed-mission schema.
- The shipped Python and browser implementations produce conformant wires for
  the registered tests.
- Wrong-context and corrupted inputs covered by the conformance suite fail
  closed.
- The shipped fixture is smaller in AVP1 form than in canonical JSON by the
  exact sizes recorded above.

## Claims not permitted by this packet

This packet does not establish:

- a universal compression ratio or a `4x` end-to-end speedup;
- model-training acceleration, lower total FLOPs, or lower inference cost;
- improved model reasoning;
- public-language, unseen-schema, or production-workload generalization;
- production security, authority correctness beyond the shipped tests, or
  production readiness;
- patent validity, freedom to operate, or legal sufficiency of the draft
  Community Engine terms;
- independent reproduction by an outside tester.

Private experimental results are intentionally excluded from the public-alpha
claim set until their complete supporting evidence is selected for publication.

## Reproduction requirement

An outside tester should follow `TESTING.md` from a clean clone and submit the
generated privacy-bounded receipt. The first independent receipt must be
preserved whether it passes or fails. A Titans Forge clean-copy run is not a
substitute for independent reproduction.

## Release authorization boundary

This file, the passing manifest, and a successful independent receipt are
release inputs. They do not authorize publication. Publication requires an
exact revision, effective license text, destination, release notes, and an
explicit operator approval recorded after the candidate is frozen.
