# ANVIL development update — September 5, 2026

ANVIL is continuing through its limited public beta. Our objective is straightforward:
**help local agents complete useful jobs reliably at substantially lower total cost.**

Compact representations remain part of the research. But fewer bytes or tokens
are not enough: the system must preserve meaning, respect permissions, and finish
the right job. Recent experiments have helped us separate those questions.

## Public beta versus ongoing research

The public reference package focuses on deterministic encoding and decoding,
semantic and authority reconstruction, context checks, a CLI, and an offline demo.
It is a bounded reference implementation—not a general-purpose agent accelerator.

The workflow, model, and cache results below come from **separate local development
experiments**. They are not features being announced as available in the current
public package, nor independently reproduced public benchmarks.

## What we have learned

### Reusing context helps, but does not fix wrong answers

In a small synthetic cache experiment, persistent prefix reuse matched a freshly
rebuilt reference on all 14 comparisons **when both used the same prefill
partition**. Warm-request timings were approximately 1.20×–1.56× faster in that
probe, including input preparation.

There is an important qualification: processing the entire prompt at once
produced a different output on one comparison. That failure remains recorded.
These measurements are not general end-to-end agent speedups, and ordinary
JSON-based systems can use the same caching technique.

### Permissions belong in executable controls, not just prompts

We added a host-side gate that rejects denied reads before assembling the data
prompt or invoking the model. In a subsequent synthetic probe, all eight denied
requests were handled correctly with zero model calls. Cache agreement and
invalidation checks passed on all 36 paired comparisons.

Authorized model reads were still weak: only **12 of 28** met the exact response
contract. Fifteen responses used Markdown fences rather than bare JSON; five of
those also contained incorrect values. Another bare-JSON response was wrong.
Formatting and semantic accuracy are separate problems, and we are treating them
that way—not silently repairing responses and calling the original test a pass.

### Some work should not go through a model at all

When a request already supplies an exact, structured object ID, deterministic
code can perform the authorized lookup directly. The experimental typed-read
path passed **1,050 synthetic outcome and access checks** without model calls.
A separate, narrowly specified JSON-wrapper adapter passed 200 generated parser
fixtures; accepting a wrapper does not certify that its contents are correct.

This is ordinary deterministic execution, not proof of better language
understanding or an ANVIL-specific compression advantage. Ambiguous language
requests remain separate and currently abstain in this offline prototype.

## Current engineering status

The local workflow regression suite now has **481 passing tests**. We also have
a development tester that keeps expected answers out of workflow inputs and
reports successful reads, denials, errors, and abstentions separately. Test
counts demonstrate regression coverage—not production reliability.

No general 4× agent speedup, improved reasoning, cheaper neural training, or
production-readiness claim is justified by these recent experiments.

## Next priorities

1. Collect fresh, independently authored tasks rather than keep optimizing the
   same synthetic examples.
2. Compare complete request-to-result workflows against an ordinary JSON system
   with the **same** permissions, deterministic executor, and available information.
3. Count selection errors, abstentions, fallback, startup, and failed jobs in
   the cost—not just successful inference time or compressed positions.
4. Move experimental capabilities into a release only after a separate review
   of correctness, privacy, packaging, and reproducibility.

The September 11 full-release date remains a target, not an automatic promotion.
The beta will continue if release-critical issues remain.

## How to help now

For the currently available package, follow the repository's
[beta tester guide](https://github.com/Titans-Forge-LLC/anvil/blob/main/BETA_TESTER_GUIDE.md)
and report reproducible results through
[GitHub Issues](https://github.com/Titans-Forge-LLC/anvil/issues).

We would also like examples of small local-agent jobs you actually want done:
what the input looks like, what counts as success, and when the agent should
refuse or ask for clarification. Use invented or independently public data only;
do not submit credentials, private prompts, customer files, or sensitive records.
The new offline workflow tester is still in development and is not yet part of
the public package.

The direction is practical: let models handle genuinely uncertain interpretation,
let trusted code handle exact execution, and make every claimed saving survive
an honest useful-job comparison.
