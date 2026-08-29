# ANVIL Public Alpha

**ANVIL** is the **Adaptive Neural Vector Instruction Language**: a research
architecture for compact, context-bound agent instructions whose meaning and
authority must survive decoding exactly.

Status: `LOCAL RELEASE CANDIDATE / NOT PUBLISHED`

Patent Pending.

Repository target: `https://github.com/Titans-Forge-LLC/anvil`

## Try the reference profile

AVP1 is a dependency-free public reference profile built from synthetic data.
It demonstrates deterministic canonicalization, compact symbols, exact semantic
and authority reconstruction, and fail-closed context binding.

```bash
cd /path/to/public_alpha
PYTHONPATH=src python3 -m anvil_alpha.cli encode \
  examples/governed_mission.json /tmp/governed_mission.avp1
PYTHONPATH=src python3 -m anvil_alpha.cli verify \
  examples/governed_mission.json /tmp/governed_mission.avp1
PYTHONPATH=src python3 -m anvil_alpha.cli benchmark \
  examples/governed_mission.json
```

Open `site/index.html` directly to use the browser demo. It makes no network
requests and does not execute mission operations.

A network-free Python installation requires `setuptools>=68` and `wheel` to be
present in the build environment before running `pip install --no-build-isolation .`.
Normal connected `pip install .` environments may obtain those declared build
requirements through standard build isolation.

## Evidence boundary

The public AVP1 demo is not the private AVD2 implementation. The separately
recorded AVD2 result encoded 14,708 canonical semantic bytes into 3,143 wire
bytes (4.6796x) on one frozen 31-directive historical Forge cohort, with 180 of
180 fields reconstructed exactly. That is a bounded byte-compression result,
not a universal token, cost, model-training, security, or production claim.

See [CLAIMS_AND_LIMITATIONS.md](CLAIMS_AND_LIMITATIONS.md).

## Independent testing

The founding-tester protocol is in [TESTING.md](TESTING.md). A privacy-bounded
receipt can be generated with:

```bash
PYTHONPATH=src python3 scripts/create_test_receipt.py \
  --output anvil-test-receipt.json
```

Use only synthetic or independently public material. Do not upload private
prompts, customer data, credentials, private Forge directives, retired-shadow
records, or patent-filing documents.

## Package boundary

This release candidate contains only:

- the AVP1 reference codec and CLI;
- a synthetic governed-mission example;
- exactness and wrong-context tests;
- an offline interactive demonstration;
- release-verification and documentation files.

It contains no private Forge directives, workflow database, retired shadow,
patent filing documents, optimized private codec, hosted service, or live
runtime integration.

## Licensing route

The reference implementation in this directory is staged for the open-source
layer under the MIT License in [LICENSE](LICENSE). The planned optimized compiler, codec, and runtime
are not included and are intended for a separate source-available community
license with a USD 10 million annual-revenue threshold. See
[LICENSE_BOUNDARY.md](LICENSE_BOUNDARY.md).

Existence of this local directory does not authorize publication.
