# Founding Tester Protocol

The first goal is independent reproduction, not a compression leaderboard.

## Track A — Clean reproduction

1. Clone the repository into a clean directory.
2. Use Python 3.9 or later and a current Node.js runtime.
3. Run:

```bash
PYTHONPATH=src python3 scripts/verify_release.py
PYTHONPATH=src python3 scripts/create_test_receipt.py \
  --output anvil-test-receipt.json
```

4. Inspect the receipt. It must report `PASS`, semantic exactness, authority
   exactness, the source commit, runtime versions, and exact byte counts.
5. Submit the receipt with the Reproduction Report issue form.

## Track B — Adversarial decoding

Try truncated, corrupted, reordered, wrong-profile, Unicode, escaped-prefix,
empty, deeply nested, and maximum-practical-size synthetic inputs. Report any
case that decodes incorrectly, fails open, becomes nondeterministic, or produces
an uncounted repair.

Do not test with credentials, personal data, customer material, private agent
instructions, or non-public Forge records.

## Track C — Independent public examples

Create a new semantic object from synthetic or already-public source material.
Record its provenance, canonical JSON size, AVP1 wire size, exactness, and any
schema or usability friction. Positive and negative compression results are both
valuable and must be preserved.

## Track D — Alternative representations

Proposals may compare alternative reversible representations using the same
semantic object and exactness requirements. Clearly separate:

- bytes from tokenizer positions;
- transport size from model-training cost;
- deterministic codec results from learned-model results; and
- public AVP1 results from private historical AVD2 evidence.

## Acceptance boundary

A clean reproduction establishes that the public reference behaves as recorded
in the tested environment. It does not establish production readiness, patent
novelty, universal compression, security, or model-training acceleration.
