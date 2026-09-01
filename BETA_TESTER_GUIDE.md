# Limited Beta Tester Guide

Thank you for testing ANVIL. The most useful contribution is a reproducible
failure or independent receipt, not a favorable headline.

## Ten-minute clean reproduction

Use a clean clone with Python 3.9 or later and a current Node.js runtime:

```bash
PYTHONPATH=src python3 scripts/verify_release.py
PYTHONPATH=src python3 scripts/create_test_receipt.py \
  --output anvil-test-receipt.json
```

The verifier must report `PASS`. The receipt intentionally excludes the source
payload, username, hostname, and filesystem paths. Inspect it before sharing.

## What to test

- a new synthetic or already-public semantic object;
- empty, Unicode, nested, repeated, and maximum-practical-size values;
- truncated, corrupted, reordered, and wrong-context wires;
- Python/browser wire parity;
- installation and documentation on a clean machine.

Do not use credentials, personal data, customer content, private agent
instructions, confidential company material, or non-public Forge records.

## What to report

Open the matching GitHub issue template and include:

- the generated receipt or its relevant privacy-reviewed fields;
- operating system, architecture, Python version, and Node version;
- exact commands used;
- expected and observed behavior;
- the smallest public or synthetic reproducer;
- whether the issue affects semantic exactness, authority exactness,
  determinism, fail-closed behavior, portability, or documentation.

Positive and negative compression results are both welcome. Keep byte counts,
tokenizer positions, model FLOPs, and wall time separate.

## Boundaries

This beta is not production software, a security certification, a universal
compression result, or evidence that ANVIL changes model reasoning. Do not use
it to authorize or execute consequential actions.
