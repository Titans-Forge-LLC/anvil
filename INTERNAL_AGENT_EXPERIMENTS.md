# What our local-agent experiments have demonstrated

September 5, 2026. Internal development evidence, not independent validation.

We use the generic label **local agent** here rather than internal agent names.
This label describes a role in controlled experiments; it does not imply several
independent models, production deployment, or customer adoption. These workflows
are separate from the public AVP1 reference codec.

## How the pieces work

There are two distinct layers:

1. **Representation:** the public AVP1 codec replaces registered keys and values
   with compact symbols, escapes literal symbols, and reconstructs the object
   under the expected profile. Profile matching and canonical decoding do not
   authenticate a sender or authorize an action.
2. **Execution:** the experimental host checks permission before exposing state
   to a model. For an already structured exact-ID read, ordinary code validates
   the request and reads the authorized value. Language requests currently
   abstain in that offline wrapper; a future resolver must earn its place through
   testing rather than silently guessing an ID.

For example, an invented typed request might be:

```json
{"operation":"read_limit","id":"object-001"}
```

The host supplies permission separately; the request cannot grant it. If denied,
the host refuses before loading the object or invoking inference. If allowed,
the deterministic reader checks the schema and returns the current value—or an
explicit error for a missing object or invalid state. This is an explanation of
the experimental interface, not a command supported by the public codec CLI.

Potential savings come from avoiding unnecessary model calls and repeated
context processing. Their value depends on the workload. Neither technique
requires a new language, so a fair JSON baseline must receive the same benefits.

## Configuration-change proposals

In one controlled development comparison, a local agent using a typed proposal
interface passed **16 of 24** evaluated trials, compared with **14 of 24** for
the comparison interface. Trials covered top-level changes, nested changes,
multiple changes, already-satisfied requests, ambiguous requests and denied work.
Each underlying case appeared in two layouts; these are correlated trials.

The typed interface passed all 16 top-level, nested, multi-change and no-change
trials. It passed **none of the eight ambiguity/denial trials**. Four ambiguous
trials produced accepted but unjustified proposals. That is a serious limit:
structural validity did not establish that the proposal was what the user wanted.

These were proposal/evaluation experiments. **No actual workspace files were
changed.** This is evidence that a local agent can sometimes propose the right
structured changes—not evidence of reliable autonomous repository maintenance.
The full candidate gate failed, and the exposed fixtures were retired from tuning.

## Read-only answers and host-side denial

In a separate synthetic read experiment, the local agent returned exactly
correct authorized responses on **12 of 28** requests. Fifteen responses used
Markdown fences instead of the required bare JSON; five of those also contained
incorrect values. One bare-JSON response contained an incorrect value too.

The surrounding host gate handled **eight of eight denied requests without
calling the model**. That success belongs to executable host policy, not to the
agent learning to obey a prompt. Both comparison arms received the same gate.

## Context reuse

A small cache diagnostic matched generated tokens on **14 of 14** comparisons
against a reference using the same prefill partition. Warm timings were about
1.20x–1.56x faster in that experiment. A full-prompt reference differed on one
comparison, which remains an unresolved equivalence boundary.

This is limited runtime engineering evidence. It is not proof of better
reasoning, general job savings, or a compression-language advantage; conventional
JSON agent runtimes can use prefix caching too.

## Work the host can do without an agent

The experimental exact-ID reader passed **1,050 synthetic outcome and access
checks** without inference. It handles a structured request, current state and
host-owned permission. Its offline wrapper abstains on language requests rather
than pretending an ID match proves intent.

These are deterministic software capabilities, not agent accomplishments.
Avoiding an unnecessary model call may be useful, but we have not measured its
advantage on a representative independently authored workload.

## What we are not claiming

- Our production agents are not demonstrated here to run on the public AVP1 codec.
- The public codec does not itself execute permissions, route tools, or interpret requests.
- Correct bytes, valid structure and correct user intent are different properties.
- Test counts and synthetic examples do not establish deployment reliability.
- These trials establish neither a general 4x speedup nor improved reasoning.

The next product test is a complete useful workflow against ordinary JSON with
the same executor, permissions, information and budgets. We will count failures,
abstentions, fallback and startup costs, and report model work separately from
host enforcement. The goal remains fewer total resources per correctly completed
job—not a larger compression headline.

## What you can reproduce today

Use the public [beta tester guide](BETA_TESTER_GUIDE.md) for the reference codec,
or run from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 scripts/verify_release.py
```

This checks the release boundary and Python/JavaScript conformance; it does not
reproduce the private workflow experiments summarized above. The corrective
candidate adds shipped-fixture cross-runtime wire coverage and makes previously
skipped Python tests discoverable by the existing test runner. General number
and Unicode interoperability remains open; fixture parity is not universal
JSON interoperability.

For useful-job testing, record the initial permitted state, request, expected
outcome, actual result, model/tool calls, failures, abstentions and total time.
Keep expected answers outside the executing agent. Use invented or public data,
not personal or customer records. Do not combine results from different workloads
into a single speedup figure.
