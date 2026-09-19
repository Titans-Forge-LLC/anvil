# Live Splash integration — September 19, 2026

ANVIL's proposal workflow now has a real-model integration smoke, not just HTTP
fixture tests. This is compatibility evidence, **not an ANVIL acceleration claim**.

## Setup

- Apple M5 Max, 128 GiB unified memory, macOS 27.0.
- Official Splash 1.0 prebuilt ARM64 release; archive SHA-256:
  `dc752f0aab8419c46fe2803a0e7059c1515e5df48def11b9d517bbbf1fb2dddc`.
- `incoai/Qwen3.8-27B-Splash`, snapshot
  `9d27070b71f7142c6b6025f03ac011d70a73cb48`; package verification passed.
- Loopback only, temporary bearer authentication, web UI disabled, 32G Metal
  allocation ceiling and 8K context limit. Server stopped after the trial.
- Temperature zero, reasoning disabled, non-streaming, output budget 512 tokens.
- Public ANVIL source at `f9d9786067f5ac5ad7c893e6314d9e37d9471b96`.

The [official Homebrew formula](https://github.com/incoai/homebrew-tap/blob/main/Formula/splash.rb)
identifies the release artifact and checksum. Homebrew was blocked locally by an
unaccepted Xcode license; the verified prebuilt package ran directly, without
accepting that agreement or changing system toolchain settings.

## Comparison and results

Used the same three requests in [compare_source_drafts.py](compare_source_drafts.py):
`normalize` mapping comprehension, `_load_json` UTF-8 BOM support, and a `_pack`
docstring. Direct HTTP and ANVIL received identical messages. Two repetitions
reversed arm order: direct then ANVIL, followed by ANVIL then direct. Server state
was retained throughout; there was no cache reset between arms.

| Measurement | Observed |
| --- | ---: |
| Completed requests | 12/12 |
| Identical text in paired direct/ANVIL requests | 6/6 |
| ANVIL structurally reviewable proposals | 6/6 |
| Requested AST transformations, unique proposals | 3/3 |
| Direct HTTP total, six requests | 5.702 s |
| ANVIL total, six requests including source/diff work | 4.872 s |
| Startup, including local package verification | 10.033 s |
| Entire run including startup, requests, bookkeeping and shutdown | 20.764 s |

Second-repetition warm timings:

| Task | Direct HTTP | ANVIL workflow |
| --- | ---: | ---: |
| `normalize` | 1.198 s | 1.201 s |
| `_load_json` | 0.225 s | 0.227 s |
| `_pack` | 1.007 s | 1.008 s |

Every pair had identical output hashes. Static AST comparison confirmed that the
three unique proposals made exactly the requested transformation: the mapping
branch retained key validation before sorting, only the loader encoding changed,
and removing the added docstring restored the original `_pack` AST. No generated
code was applied or executed. This is stronger than parsing, but not a general
behavioral benchmark or proof of coding ability.

## What these numbers do not establish

The direct arm encountered cold prefixes first. Its higher aggregate time is not
an ANVIL advantage. Warm differences were only roughly 1–4 ms in this tiny trial;
they do not establish a stable overhead distribution. Model download time is
excluded from the run totals; startup and shutdown are included separately above.
Human review time was not measured, so these are not complete job-cost results.

Splash owns DFlash, target verification and KV state. ANVIL currently adds the
source-bound proposal/revision workflow. The HTTP path does not pass ANVIL source
draft tokens into the engine. Do not multiply these timings by the older MLX
source-drafting result or compare different models as an architecture ablation.

## Next useful implementation

Update: the [isolated engine-hook screen](SPLASH_SOURCE_ENGINE_SCREEN.md) is now
complete. It preserved outputs but did not earn default adoption. The proposal
below records the experiment that was undertaken.

Build one isolated engine hook for a caller-provided source draft, with ordinary
Splash as the baseline. Reuse the engine's target verification and rollback; do
not transplant MLX cache logic into its recurrent/drafter state. First compare
source drafting **versus** existing DFlash on the same edit tasks, rather than
stacking both and obscuring attribution. Add switching only if that comparison
shows a useful complementary case. Keep the working HTTP workflow available.
