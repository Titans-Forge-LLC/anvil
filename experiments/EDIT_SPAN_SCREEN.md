# Exact edit spans: an opt-in workflow improvement

September 19, 2026. Instead of regenerating a whole function, the model emits
one literal `old` / `new` replacement. ANVIL reconstructs the source-bound
proposal, validates its structure, and returns a diff without applying it.
This is ordinary structured editing, not a new compression or decoding claim.

## Live comparison

Same stock Splash 1.0, supported Qwen3.8-27B package and three public maintenance
requests as the previous experiments. One shared server; order was replacement,
edit, edit, replacement. Model reasoning disabled, temperature zero, output limit
512, context 8K, Metal budget 32 GiB, on the 128 GiB M5 Max. No engine hook was
enabled. The two formats receive the same source and task, but different format
instructions. No answers or evaluator labels enter the model prompt.

| Six requests per format | Whole function | Edit span |
| --- | ---: | ---: |
| First-pass requested AST transformation | 6/6 | 6/6 |
| Structural fallback requests | 0 | 0 |
| Output tokens | 650 | 316 |
| Request plus task-check time | 5.723 s | 4.029 s |

That is 51.4% fewer output tokens and 29.6% less request-plus-check time in this
screen. Input was not reduced: the edit-format instruction added 76 prompt
tokens per task according to the server logs. Prefill, parsing, reconstruction,
source reads/checks, diff creation and evaluator work are included in elapsed
request/check time. The model may choose different text or docstrings in the
two formats; the criterion here is the exact requested AST transformation, not
identical generated output strings or target-distribution equivalence.

The second, warm repetition alone:

| Task | Whole function | Edit span |
| --- | ---: | ---: |
| Mapping comprehension | 1.206 s | 0.480 s |
| UTF-8 BOM encoding change | 0.230 s | 0.330 s |
| Add packing docstring | 1.014 s | 0.822 s |

The small encoding change **lost** despite fewer output tokens. Envelope and
format overhead can outweigh the saved output. Keep both formats available;
there is no claimed universal routing rule.

Shared server startup was 10.048 s. The comparison itself took 9.756 s; the whole
trial including server startup/shutdown took 20.018 s. Downloads, human review,
code application and behavioral execution are excluded. This is not a completed
agent-job cost benchmark. The three requests are known development examples,
not a new independent corpus; repeated requests and shared cache are disclosed.

## Reproduce

Start a supported local Splash server separately, set `SPLASH_API_KEY` in both
processes if authentication is enabled, then run:

```sh
python experiments/compare_edit_proposals.py --model incoai/Qwen3.8-27B-Splash
```

The runner prints metadata only. It gives structurally invalid edit proposals
one counted whole-function fallback. Both attempts' tokens and time count;
task-quality failures remain failures and do not trigger hidden retries.
The workbench itself never retries automatically. No generated code is applied
or executed. [The receipt](edit_span_screen.json) records the measured runner
and workbench hashes. A final deterministic hardening check was added after the
timing run to reject removal of the selected function's terminal newline; it
does not change prompts or the successful transformations measured here.

## Decision

Ship this as an opt-in experimental mode, with whole-function proposals still
the default. Next use it on fresh bounded maintenance requests and measure
completed work, review and fallback costs. The experimental source-draft engine
remains separate; its timing cannot be multiplied by this format result.
