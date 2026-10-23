# ANVIL Limited Public Beta

**ANVIL** (Adaptive Neural Vector Instruction Language) is an experimental local
agent project. Its current workbench helps you propose a Python change, inspect
its scope and diff, save it, and resume review without asking the model again.

Status: `LIMITED PUBLIC BETA`

**[Start with one small edit](experiments/START_HERE.md)**, or read the
[workbench reference](experiments/WORKBENCH.md).

### Install this development preview

From this checkout, install into a virtual environment outside the repository:

```sh
python3 -m venv ../anvil-env
../anvil-env/bin/python -m pip install .
../anvil-env/bin/anvil-workbench --help
```

On Windows, use `py -3 -m venv ..\anvil-env`, then
`..\anvil-env\Scripts\python -m pip install .` and
`..\anvil-env\Scripts\anvil-workbench --help`.

Run `anvil-workbench` from that environment against your own project. The equivalent
module command is `python -m anvil_workbench`. Installation includes the workbench
and optional check-runner code, but does not install MLX, a model, or a server.
The original `anvil` and `anvil-alpha` codec commands are unchanged. Installing a
development checkout is not a new tagged release or a PyPI publication.

- Use an existing local Splash or TensorFold server, or the in-process MLX backend.
- Opt in to bounded, in-process exact HTTP response replay for repeated drafts.
  It avoids another identical request, not fresh sampling or fresh review.
  [HTTP response reuse](experiments/WORKBENCH.md#replay-an-identical-http-response-without-another-request).
- Select one function or 2–4 related functions in the same file. A multi-function
  proposal is retained as a unit; invalid members reject the whole transaction.
- Save a source-bound checkpoint, close the session, and resume review offline.
  Changed source blocks reuse. Checkpoints contain code; keep them private.
- Development preview: save a single-function **job capsule** with its intent
  and resume an untrusted draft after unrelated edits. No approval or test
  result is restored; fresh checks and review are required.
  [Job continuation](experiments/WORKBENCH.md#resume-a-single-function-job-after-unrelated-edits).
- Explicitly export a new patch for your normal Git workflow. ANVIL does not
  apply changes. Reviewable does not mean correct.
- Optionally run declared Python checks against a disposable candidate snapshot
  on macOS, then request one correction and recheck. Execution is disabled unless
  started with a test plan; network access and live-source writes are denied.
  [Run checks and correct once](experiments/WORKBENCH.md#run-declared-checks-and-correct-once-macos).

The TensorFold, multi-function and checkpoint workflow is available from
`main`. These features remain an experimental preview, not a new tagged release.
See [PR #31](https://github.com/Titans-Forge-LLC/anvil/pull/31) for the integration
history and checks.

The practical goal is less repeated model work per useful job. We have not
established a general end-to-end speedup or autonomous coding reliability.
HTTP backends own their generation, caches and speculative decoding; those
engine gains are not ANVIL inventions. ANVIL adds the source-bound review workflow.

AVP1, the original reversible mission codec, remains available below as a
separate research reference. It does not enforce permissions or run agents.

Research and negative results: [local-agent evidence](INTERNAL_AGENT_EXPERIMENTS.md),
[repair loop](experiments/REPAIR_LOOP_SCREEN.md),
[atomic edits](experiments/ATOMIC_EDIT_SCREEN.md),
[single-span edits](experiments/EDIT_SPAN_SCREEN.md),
[Splash smoke](experiments/SPLASH_LIVE_SMOKE.md), and
[source-draft experiment](experiments/SPLASH_SOURCE_ENGINE_SCREEN.md).

The beta remains open. The earlier September 11 target was not a full-release
promotion. We are shipping incremental previews while keeping measured results
and unsupported claims separate.

If you saved wires from the earlier browser encoder, an offline migration command
can convert its exact canonical wires to the corrected format. From the repository
root, use a new output file and keep your original:

```sh
(set -C; node scripts/migrate_legacy_browser.mjs < old-wire.avp1 > migrated-wire.avp1)
```

The command accepts only the registered `AVP1/governed-mission-v1` profile. On
refusal it exits with status 1 and writes no wire to stdout; inspect and remove
any empty output file created by shell redirection. It never runs automatically.
Normal decoding continues to reject noncanonical old wires. This repairs known
browser ordering cases; it does not recover precision lost before encoding or
establish universal Python/JavaScript number compatibility.

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

The CLI also accepts `-` for standard input/output, so commands can be piped:

```sh
PYTHONPATH=src python3 -m anvil_alpha.cli encode examples/governed_mission.json - | \
  PYTHONPATH=src python3 -m anvil_alpha.cli decode - -
```

`benchmark -` reads JSON from stdin. For `verify`, either the JSON source or the
wire may be `-`, but not both: one stdin stream cannot supply both documents.
Omitting the output still writes to stdout. To access a file literally named `-`,
use its absolute path (`./-` is normalized to `-` by the path parser).

Named output files use same-directory temporary writes and atomic replacement:
encoding/write/promotion failures leave the old output intact. Existing regular
file permissions are preserved; new files use private temporary-file permissions.
Symlinks and other nonregular destinations are refused, and missing parent
directories are not created. Stdout/newline behavior is unchanged. This is not
a crash-durability or concurrent-filesystem-race guarantee.

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

The installed Python wheel contains the AVP1 codec and CLI, the proposal-only
workbench and its opt-in check runner, and package metadata. The checkout also
includes public examples, tests, recorded development screens, documentation,
release-verification tools and an offline browser demonstration. Those extra
checkout materials are not installed as runtime packages.

It contains no private Forge directives, workflow database, retired shadow,
patent filing documents, optimized private codec, hosted service, or live
runtime integration.

## Licensing route

The reference implementation in this repository is released under the MIT
License in [LICENSE](LICENSE). Optimized private components are not included
and are not licensed by this repository. See
[LICENSE_BOUNDARY.md](LICENSE_BOUNDARY.md).
