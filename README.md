# ANVIL Limited Public Beta

**ANVIL** is the **Adaptive Neural Vector Instruction Language**: a research
architecture for compact, context-bound agent instructions whose meaning and
authority must survive decoding exactly.

Status: `LIMITED PUBLIC BETA`

Latest: [Development update — September 5, 2026](DEVELOPMENT_UPDATE_2026_09_05.md).

Research detail: [What our local-agent experiments have demonstrated](INTERNAL_AGENT_EXPERIMENTS.md).

Beta window: public testing is planned through approximately September 11,
2026. The full-release date is a target, not an automatic promotion: semantic
or authority failures, privacy issues, or unresolved release-critical defects
will extend the beta.

Patent Pending.

Repository target: `https://github.com/Titans-Forge-LLC/anvil`

## Join the beta

The beta is built around public testing rather than a claim of finished
production software. Clone the repository, run the ten-minute verifier, and
submit either a clean reproduction or a small synthetic/public experiment:

```bash
PYTHONPATH=src python3 scripts/verify_release.py
PYTHONPATH=src python3 scripts/create_test_receipt.py \
  --output anvil-test-receipt.json
```

- [Beta tester guide](BETA_TESTER_GUIDE.md)
- [Testing tracks](TESTING.md)
- [Report a reproduction](https://github.com/Titans-Forge-LLC/anvil/issues/new?template=reproduction.yml)
- [Report an experiment](https://github.com/Titans-Forge-LLC/anvil/issues/new?template=experiment.yml)

## Try the reference profile

AVP1 is a dependency-free public reference profile built from synthetic data.
It demonstrates deterministic canonicalization, compact symbols, exact semantic
and authority reconstruction, and fail-closed context binding.

```bash
git clone https://github.com/Titans-Forge-LLC/anvil.git
cd anvil
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

The public AVP1 beta is not the private AVD2 implementation. The separately
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

This beta candidate contains only:

- the AVP1 reference codec and CLI;
- a synthetic governed-mission example;
- exactness and wrong-context tests;
- an offline interactive demonstration;
- release-verification and documentation files.

It contains no private Forge directives, workflow database, retired shadow,
patent filing documents, optimized private codec, hosted service, or live
runtime integration.

## Licensing route

The reference implementation in this repository is released under the MIT
License in [LICENSE](LICENSE). Optimized private components are not included
and are not licensed by this repository. See
[LICENSE_BOUNDARY.md](LICENSE_BOUNDARY.md).
