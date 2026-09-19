# Persistent coding workbench — experimental preview

Keep a local model resident while requesting related edits. ANVIL retains an
exact-response cache, token-identical causal KV prefixes, and the last complete
answer as a candidate draft. The target verifies draft tokens in blocks; on the
first mismatch it rolls back rejected KV rows and continues normally.

This is a single-file proposal loop, not an autonomous coding agent.
It reads only the file you select, returns replacement text and a review diff,
and never applies changes, executes generated code, or calls tools. No server
or telemetry is started. Treat output as untrusted code requiring review.

## Run

Requires an Apple Silicon Mac, Python 3.10+, MLX and mlx-lm, and an existing
local MLX-format Qwen2/Qwen2.5 model. The codec needs none of these.
Install optional dependencies in a separate virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install mlx==0.31.2 mlx-lm==0.31.3
python experiments/workbench.py --model /absolute/path/to/local/model
```

After the `ready` JSON line, enter one JSON object per line:

```json
{"file":"examples/workbench_sample.py","instruction":"Return zero for empty input while preserving other behavior.","max_tokens":512}
```

Use the supplied exercise or select your own file. Start with a small file:
source is limited to 32 KiB and prompt plus generation to 4,096 tokens.
The entire replacement must fit the output budget. Enter another self-contained
request to get a follow-up proposal; the process keeps its model and caches.
Requests reread the selected file, not the last proposal. Review and save an edit
yourself before asking for a change to that edited version. Ctrl-D ends the loop.

Output includes replacement `text`, completion status, `diff_preview`, source
SHA-256, total request time, completion time, exact-cache hits, reused prefix
positions, and verified/scored draft tokens. The diff is for inspection, not an
automatic patch application interface (especially without a final newline).
A changed source, incomplete answer, or Markdown-wrapped answer does not receive
a reviewable diff. `reviewable` means ready for human inspection, not correct,
safe, tested, or approved.

No prompts or answers are saved automatically. Redirected output contains source
code: do not upload private transcripts when reporting a bug. Model loading is
reported separately; include it in cold-start comparisons.

## Compare without draft reuse

Add `--ordinary` for the same target, exact-response cache and causal-prefix
cache without draft verification. Run the same file snapshots and instructions
in each mode. Count load plus total request time for cold use, and total request
time for resident use. Include rejected drafts and failures. Compare completed
edits and behavior, not just generation rates.

Greedy FP32 computation is the initial adapter. Block and scalar computation can
have different floating-point behavior, so universal token parity is not claimed.
Recurrent, rotating, quantized KV and sliding-window caches are rejected. Other
architectures are not supported merely because their model name contains Qwen.
No weights are distributed. Loading disables Hub downloads and remote model
code, but is not an OS network sandbox. Use only trusted local model artifacts.
The local smoke used MLX 0.31.2, mlx-lm 0.31.3, transformers 5.5.4 and
tokenizers 0.22.2. Hosted CI checks the model-independent logic, not GPU inference.

## Evidence and remaining work

The preceding prototype's four authored requests (three related changes and one
exact repeat), run twice in reversed mode order on a local 14B model, took
**22.548 s ordinary versus 15.846 s with draft reuse**: 29.7% less completion
time, or 1.42x. Both modes had identical outputs in all eight pairs; all sixteen
proposals passed narrow behavior checks. Shared model loading took 5.363 s,
excluded from those completion totals. This is a one-function maintenance
experiment, not a general coding speedup or a result measured on this new CLI.

The new CLI's two-request sample smoke completed with the installed 14B model:
2.153 s loading, then 0.634 s and 0.430 s total request time. The second request
reused 105 prefix positions and verified 13 of 16 scored draft tokens before
falling back. Both responses completed and source stayed unchanged. Inspection
also found that the model removed the sample's introductory comments. This is
an integration smoke, not a speed comparison or a code-quality qualification;
generated code was not executed. Eight dependency-free tests cover block
mismatch/rollback, full acceptance, exact hits, output-budget identity,
incomplete output, recovery after error, position corruption and stale files.

The useful next feedback is one small real editing job, its follow-up, whether
the changes worked, and total time in each mode. A bad draft can be slower.
Larger-file editing and modern recurrent-model adapters remain future work;
the stable codec and its claims are unchanged.

The public preview code is MIT licensed with the rest of this repository.
Unpublished optimizations, private datasets and model weights are not included.
