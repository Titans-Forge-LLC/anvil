# ANVIL v0.2.0-beta.1

ANVIL is an experiment in making structured agent instructions compact without
allowing their meaning or authority to drift during decoding.

This limited public beta ships AVP1, a small synthetic reference profile that
you can inspect, encode, corrupt, decode, and reproduce locally. The goal of the
beta is not to present finished production software. It is to make the core
idea falsifiable in public and collect independent failures.

Public beta testing is planned through approximately September 11, 2026. That
is a target for the full release, not a promise to promote despite unresolved
release-critical failures.

## Try it

```bash
git clone https://github.com/Titans-Forge-LLC/anvil.git
cd anvil
PYTHONPATH=src python3 scripts/verify_release.py
PYTHONPATH=src python3 scripts/create_test_receipt.py \
  --output anvil-test-receipt.json
```

The repository also includes an offline browser demonstration in
`site/index.html`.

## What we want tested

- clean installation and reproduction across operating systems;
- semantic and authority exactness;
- wrong-context and corrupted-wire refusal;
- independently authored synthetic or public examples;
- negative compression results and schema friction;
- alternative reversible representations;
- the optional blinded reasoning-signature measurement harness.

## What this release establishes

On the single shipped synthetic fixture, canonical JSON is `737` bytes and the
AVP1 wire is `565` bytes, a `1.3044x` byte ratio. Python and browser reference
implementations agree on the registered wires, and the registered wrong-context
checks fail closed.

## What this release does not establish

It does not establish universal compression, production security, lower model
cost, a `4x` end-to-end speedup, improved reasoning, unseen-language
generalization, or production readiness. Historical and private research
results do not silently transfer to AVP1.

Use only synthetic or independently public material when testing. Do not post
credentials, customer data, private prompts, confidential company material, or
non-public Forge records.

Patent Pending. The shipped reference implementation is MIT licensed; separate
private optimized components are not included.
