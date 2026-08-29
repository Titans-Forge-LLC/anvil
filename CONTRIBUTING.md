# Contributing to the ANVIL Open Reference

ANVIL is currently a research alpha. Reproduction failures, adversarial cases,
independently authored public examples, documentation improvements, and small
reference-code fixes are welcome.

## Before contributing

- Use only synthetic data or material you are authorized to publish.
- Do not submit credentials, customer data, private prompts, private Forge
  directives, patent-filing material, or confidential benchmark corpora.
- Read `CLAIMS_AND_LIMITATIONS.md` and preserve its claim boundaries.
- Search existing issues and discussions before opening a duplicate.

Security vulnerabilities should follow `SECURITY.md`, not a public issue.

## Reproduce first

```bash
PYTHONPATH=src python3 scripts/verify_release.py
PYTHONPATH=src python3 scripts/create_test_receipt.py \
  --output anvil-test-receipt.json
```

The receipt deliberately excludes usernames, hostnames, filesystem paths, and
source payload contents. Inspect it before attaching it to an issue.

## Pull requests

Keep pull requests focused and include:

- the problem being solved;
- the evidence or test that failed before the change;
- tests for changed behavior;
- the exact verification command and result; and
- any effect on compatibility, wire format, authority reconstruction, or
  performance claims.

AVP1 wire-format changes require an explicit version decision. A passing test
suite alone does not authorize a silent compatibility break.

## Developer Certificate of Origin

All commits must be signed off under the Developer Certificate of Origin 1.1
included in `DCO`. Create the sign-off with:

```bash
git commit -s
```

The sign-off certifies your right to contribute the work. It is not a copyright
assignment.

The future BSL Community Engine will use a separate contribution process and is
not covered by this policy.
