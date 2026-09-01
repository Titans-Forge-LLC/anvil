# ANVIL Limited Public Beta Evidence Packet

Status: `LIMITED PUBLIC BETA EVIDENCE / RELEASE-BOUND`

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

The release manifest records the exact public file hashes and the Python and
JavaScript conformance results for the tagged revision. Testers generate a
fresh, privacy-bounded receipt with `scripts/create_test_receipt.py`; no stale
machine-specific build receipt is shipped as current evidence.

On the single shipped synthetic fixture, the corrective candidate records 737
canonical JSON bytes, 565 AVP1 wire bytes, a 1.3044x byte ratio, exact semantic
reconstruction, and exact authority reconstruction.

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

Private experimental results are intentionally excluded from the public-beta
claim set until their complete supporting evidence is selected for publication.

## Reproduction requirement

An outside tester should follow `TESTING.md` from a clean clone and submit the
generated privacy-bounded receipt. The first independent receipt must be
preserved whether it passes or fails. A Titans Forge clean-copy run is not a
substitute for independent reproduction.

## Release authorization boundary

This file and the passing manifest are release inputs. An independent receipt
is a primary beta objective, not a prerequisite to opening the beta. Promotion
to a full release requires an exact revision, beta evidence review, effective
license text, release notes, and explicit operator approval.
