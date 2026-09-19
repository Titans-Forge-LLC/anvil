# ANVIL Limited Public Beta

**ANVIL** is the **Adaptive Neural Vector Instruction Language**: a research
architecture for compact, context-bound agent instructions whose meaning and
authority must survive decoding exactly.

Status: `LIMITED PUBLIC BETA`

Latest: [Try the persistent coding workbench preview](experiments/WORKBENCH.md).
Opt-in atomic `"format":"edits"` can change several spans without regenerating
the whole function. [One adaptive development replay](experiments/ATOMIC_EDIT_SCREEN.md)
passed with lower request/check time, after two failed initial attempts. It is
not a general speedup or competitor benchmark; whole-function output stays default.
New opt-in `"format":"edit"` requests one exact source-bound change rather than
a whole function. [A small live screen](experiments/EDIT_SPAN_SCREEN.md) used
51.4% fewer output tokens and 29.6% less request/check time; one task was slower.
It keeps a local model resident, verifies reused drafts, and returns reviewable
single-file edit proposals. Optional Apple Silicon dependencies; no automatic
code execution or file changes. This experimental track is separate from AVP1.
The workbench also has a loopback Splash API adapter: engine-owned generation
with ANVIL proposals/revisions. A [live 27B smoke](experiments/SPLASH_LIVE_SMOKE.md)
completed 12 requests with six identical direct/ANVIL output pairs. The API
adapter does not enable ANVIL token-level drafting inside Splash.
An [isolated source-draft engine experiment](experiments/SPLASH_SOURCE_ENGINE_SCREEN.md)
preserved baseline outputs but showed no meaningful aggregate cost advantage;
it remains experimental and is not enabled in this package.

Research detail: [What our local-agent experiments have demonstrated](INTERNAL_AGENT_EXPERIMENTS.md).

The beta remains open. The earlier September 11 target was not a full-release
promotion. We are shipping incremental previews while keeping measured results
and unsupported claims separate.

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
