# ANVIL Reasoning-Signature Pilot

This offline pilot asks whether representation changes an agent's observable
decision behavior, rather than merely reducing bytes or positions.

It compares three conditions over identical semantic missions:

- `canonical_json`: the canonical semantic object;
- `avp1_raw`: the exact AVP1 wire; and
- `avp1_decoded`: the AVP1 wire decoded before inference.

The decoded condition separates codec and orchestration effects from effects of
the compact causal sequence. Raw AVP1 is intentionally not evidence of changed
reasoning by itself: a generic model may simply be unfamiliar with the syntax.

The response is a concise decision record, not private chain-of-thought. It
contains a final disposition, executable and blocked step identifiers, required
checks, and optional aggregate telemetry such as tool calls or revisions.

## Prepare a blinded pilot pack

```bash
PYTHONPATH=src python3 scripts/reasoning_signature.py prepare \
  --cases experiments/reasoning-signature/cases.json \
  --trials /tmp/anvil-reasoning-trials.json \
  --key /tmp/anvil-reasoning-key.json \
  --seed 17
```

Keep the key away from the responding agent. An external runner supplies one
JSON response per trial. Score that JSON array with:

```bash
PYTHONPATH=src python3 scripts/reasoning_signature.py score \
  --key /tmp/anvil-reasoning-key.json \
  --responses /tmp/anvil-reasoning-responses.json \
  --output /tmp/anvil-reasoning-report.json
```

Use `oracle` only to verify the measurement pipeline. An oracle pass is not
model evidence:

```bash
PYTHONPATH=src python3 scripts/reasoning_signature.py oracle \
  --key /tmp/anvil-reasoning-key.json \
  --output /tmp/anvil-reasoning-oracle.json
```

For a local key-isolated Ollama run, pass only the blinded trials file to the
runner. Never place the answer key in the runner's directory or arguments:

```bash
PYTHONPATH=src python3 scripts/run_reasoning_signature_ollama.py \
  --trials /tmp/anvil-reasoning-trials.json \
  --model MODEL_NAME \
  --output /tmp/anvil-reasoning-MODEL_NAME.json
```

The runner disables model thinking output, stores only the concise decision
record and aggregate telemetry, refuses to overwrite a prior result, and
unloads the model after the final trial.

The frozen contract in `contract.json` defines the claim boundary and the
minimum evidence required before using the phrase “changes reasoning.”
