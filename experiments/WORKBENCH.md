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

### Use an existing local Splash server

```sh
python experiments/workbench.py --backend splash --splash-url http://127.0.0.1:8000
```

Use the same file/function requests and `revise` IDs described below. This client
path needs only Python, not MLX. An optional `--model` identifies the package
already served; it does not download it. Set `SPLASH_API_KEY` in both processes
if the server requires authentication. No key, request body or server error body
is logged by the adapter. Output proposals can contain private code; do not
publish them inadvertently.

This integration delegates generation to Splash's documented non-streaming chat
completion API with reasoning disabled. Splash owns its model, learned drafter,
KV cache and kernels; ANVIL owns the source-bound proposal/revision workflow.
ANVIL's MLX `--source-draft` and `--ordinary` flags are rejected on this backend.
An HTTP wrapper does **not** combine ANVIL source verification with DFlash.
That requires a separate engine-level candidate-verification hook and correct
target/drafter state synchronization. Unknown engine counters are reported as
null, not invented as zero or one. HTTP request counts and elapsed time are local
measurements. Server model-loading cost is not measured by this adapter.

Only literal loopback HTTP endpoints are accepted (127.0.0.1 or ::1); proxies
and redirects are disabled. The server is a trusted local dependency: ANVIL
does not attest its identity or sandbox its internals. Truncated outputs are
incomplete; tool-call/refusal/malformed responses are rejected. There are no
automatic retries, server installs, downloads, server restarts or file writes.
The startup `ready` event means the client is accepting requests, not that the
server has passed a readiness check.

Status: fixture tests include proposal revision and failure boundaries. A
[live Splash 1.0 / 27B smoke](SPLASH_LIVE_SMOKE.md) completed 12 requests with
six identical direct/ANVIL output pairs. Live revision behavior and engine-level
combined source drafting remain unqualified. This is not an ANVIL speedup claim.
Follow [upstream installation and serving instructions](https://github.com/incoai/splash#quick-start)
to start a server before using the adapter. Then compare the same editing requests
directly and through ANVIL, counting review, retries, startup and total request
cost. Do not multiply independent speedup headlines.

### Use the in-process MLX adapter

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
whole-file source is limited to 32 KiB and MLX prompt plus generation to 4,096 tokens.
Named-function mode accepts modules up to 1 MiB while the selected function and
its replacement remain limited to 32 KiB. Only that function enters the model
prompt. The complete module remains hash-bound and is reread after generation;
unchanged surrounding text is preserved in the returned proposal. Eight retained
revision entries can therefore hold up to roughly 8 MiB of source text, plus
Python object overhead. Backend context/token limits still apply.
The entire replacement must fit the output budget. Enter another self-contained
request to get a follow-up proposal; the process keeps its model and caches.
Ordinary requests reread the selected file. To revise a proposal without touching
disk, use its returned `proposal_id`:

```json
{"revise":"p1","instruction":"Keep that change, and preserve the original docstring.","max_tokens":512}
```

The revision uses the parent's replacement as source and returns a combined diff
against the original disk file. It inherits the parent's file and symbol; changing
either is rejected. The original file hash must still match, otherwise start a
new request. Only the eight most recent reviewable proposals are kept in this
process; IDs expire on eviction or restart. Incomplete/rejected responses do not
get IDs. There is still no apply or execution command. Ctrl-D ends the loop.

For a small edit inside a larger Python file, select a top-level function:

```json
{"file":"src/anvil_alpha/codec.py","symbol":"normalize","instruction":"Review key validation and preserve all other behavior, annotations and docstring.","max_tokens":512}
```

Only that function is sent as source context. Its surrounding module is retained
verbatim by the host when composing `replacement_text`. The generated replacement
must parse as exactly one function of the same name and kind; otherwise no
reviewable replacement is returned. Imports and other globals are not supplied,
so include necessary context in your instruction. Nested functions and methods
are not selectable in this preview. File size and generation limits still apply.

### Opt-in exact edit spans

Use `"format":"edit"` with a named function to request only a change:

```json
{"file":"src/anvil_alpha/cli.py","symbol":"_load_json","format":"edit","instruction":"Accept UTF-8 JSON with or without a BOM using utf-8-sig; preserve everything else.","max_tokens":512}
```

The model returns `{"old":"...","new":"..."}`. ANVIL requires a nonempty,
unique literal match inside that function, then reconstructs the proposal while
preserving surrounding text. Duplicate JSON keys, extra fields, ambiguous or
missing anchors, no-ops, NULs, invalid reconstructed functions and lost terminal
newline boundaries are rejected. No fuzzy matching, guessed offsets, multiple
edits or automatic fallback. To insert text, the model replaces an existing
anchor with that anchor plus the insertion. Empty `new` permits deletion.

The raw envelope remains in `text`; the reconstructed full file is in
`replacement_text`. Review that file/diff, not just the envelope. The host binds
each result to `source_sha256` (disk file), `base_sha256` (current proposal base)
and `selected_sha256` (selected function). These hashes are not authentication
or execution permission. Source is rechecked after generation. A `revise` request
inherits the parent's format unless explicitly overridden. No patch is applied.

The default remains `replacement`. Edit mode requires `symbol` and cannot be
combined with raw MLX source drafting. Backend tokenization of a JSON edit is not
the same as tokenization of source code.

In the [small live comparison](EDIT_SPAN_SCREEN.md), spans reduced emitted tokens
and total request time while passing all six task-specific AST checks. The tiny
loader task was slower, so do not assume this is always the better format.

### Atomic multi-edit proposals (opt-in)

Use `"format":"edits"` when a change touches several places in one function:

```json
{"file":"examples/workbench_sample.py","symbol":"normalize","format":"edits","instruction":"Make the requested changes while preserving unrelated behavior","max_tokens":1024}
```

The model returns `{"edits":[{"old":"...","new":"..."}, ...]}` with 1–16
literal edits. All anchors resolve against the same original selected function,
not against text inserted by earlier edits. Ambiguous, missing or overlapping
anchors reject the entire proposal. Adjacent edits are allowed. Existing source
hash, syntax, scope, size and newline checks still apply, including revisions.
No edits are written or executed; review the reconstructed diff yourself.

The [first multi-edit experiment](ATOMIC_EDIT_SCREEN.md) failed twice before a
task-independent envelope example and lower output cap produced a correct,
faster adaptive replay. This mode is experimental, not the default. Do not
assume speed or correctness from a smaller-looking representation. Splash
responses now include `input_tokens` when the server reports it; missing counts
remain `null` and are never estimated.

Unchanged reconstructed proposals are rejected without a diff or revision slot.
For revisions, "unchanged" means equal to the parent proposal, not the disk file;
deliberately reverting a parent to disk content is still a valid proposal.

CLI request lines are read in bounded chunks with a maximum of 16,384 characters
including the line terminator. Oversized lines emit one error and are drained;
the next valid request remains usable. No fragment is dispatched. Draining is
memory-bounded, not time-bounded: an input stream that never supplies a newline
or EOF can still keep the reader waiting. This is a local CLI, not a network service.

### Opt-in reasoning for a repair

Splash defaults to `none`. Set a session default with `--reasoning-effort low`,
or override just one request/revision:

```json
{"revise":"p1","instruction":"The boundary test failed: explain the observed failure here and request a correction.","reasoning_effort":"low","max_tokens":4096}
```

Use the actual returned proposal ID, not necessarily `p1`. Omitted or null effort
uses the client's configured default; an override is not sticky. Valid effort
names are `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`. Support and
meaning depend on the served model/template; errors are not silently retried
with thinking disabled. Non-default CLI effort is rejected for MLX before loading.
Reasoning consumes output budget and time; `output_tokens` is the server's total
completion count, not just visible code. `reasoning_effort` is recorded in results.
The product does not run tests or choose an escalation policy for you.

In [one repair-loop replay](REPAIR_LOOP_SCREEN.md), both fast repairs failed;
both reasoning-enabled repairs passed. That supports testing this option, not
enabling it universally or claiming a general repair-success rate.

### First real maintenance use

The function mode proposed the shipped `normalize` key-validation repair on the
existing 14B adapter: 177 output tokens, 3.667 s total request time, plus 2.149 s
model loading. This was a first request with no reused draft, not a speedup test.
The maintainer reproduced three mixed-key failures, reviewed the proposal, and
applied its minimal change: validate all mapping keys before sorting. The new
regression test covers both key insertion orders, nested input and integer-only
keys. Review, test and application time are not included in the inference timing.
The workbench itself did not execute or apply the proposal.

### Revision workflow result (including failure)

On a second real maintenance task, `_write` needed to avoid adding redundant
newlines. With JSON-wrapped source, the first proposal missed stdout and its
revision incorrectly doubled a newline escape. Ordinary generation produced
the same failures, so neither proposal was applied. Source is now supplied
verbatim to avoid that extra escaping layer; this is not an injection defense.

With verbatim source, the initial proposal still missed stdout. One explicit
revision produced the correct combined change in both ordinary and draft modes.
The maintainer reviewed and applied it; behavior tests cover empty text, existing
newlines, blank lines, Unicode, stdout and files. A syntactically reviewable
proposal is not necessarily correct, and speed is not a substitute for review.

In that single paired run, ordinary requests took 1.377 + 1.342 seconds;
draft-mode requests took 1.341 + 1.081 seconds. The revision verified 18 draft
tokens. Shared loading took 2.746 seconds. These are request timings, not a
general speedup claim: fixed ordinary-first order, one example, and review/test
time excluded. The failed JSON-framed trials are retained here rather than
counted as successful work. No private source or model paths are published.

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

### Optional first-request source drafts

Add `--source-draft` to use the selected source code (or parent proposal on a
revision) as the candidate instead of the previous answer. Every candidate token
is target-checked. The first mismatch rolls back and falls back as before; there
is no assumption that unchanged-looking source must remain correct. Tokenization
is counted in request time. Source containing special control tokens is not used
as a draft. The ordinary flag and source-draft flag are mutually exclusive.

```sh
python experiments/workbench.py --model /absolute/path/to/local/model --source-draft
python experiments/compare_source_drafts.py --model /absolute/path/to/local/model
```

The comparison uses three declared requests on public functions, fresh sessions
per request, and two repetitions with reversed arm order. Both arms have the same
resident target and cache implementation. It prints metadata and output hashes,
not proposal bodies. It does not execute or apply generated code.

[Recorded screen](source_draft_screen.json), existing Qwen2.5-14B adapter:

| Editing request | Ordinary total (s) | Source draft total (s) |
|---|---:|---:|
| Late mapping-loop change | 8.220 | 4.223 |
| JSON loader encoding change | 1.118 | 0.591 |
| Early docstring insertion | 4.776 | 4.446 |
| **Total across both repetitions** | **14.114** | **9.260** |

All six paired outputs were complete and text-identical. Request time decreased
34.4% in this small screen (1.52x); shared loading was 2.295 s and the full
two-arm campaign took 25.730 s. Model forward calls fell from 682 to 366, but
block calls do more work than single-token calls: this is not a FLOP reduction
measurement. Review and behavior-testing time are excluded, and syntax/text
agreement does not establish task correctness. Benefits were much smaller for
the early edit. Other requests can lose time; the option remains experimental.

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
