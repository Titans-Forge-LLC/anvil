# Security Policy

## Supported version

Only the most recent tagged ANVIL Open Reference beta is supported. This is a
research implementation and is not qualified for safety-critical, production,
or authority-enforcement use.

The experimental workbench is non-executing by default. Opting in with a local
test plan enables a macOS-only sandboxed Python check runner. It denies network
access and host writes, but trusts the Python runtime, OS, and operator-selected
test entry point. It is not a VM, remote attestation, comprehensive resource
isolation, or proof that candidate code cannot deceive in-process tests. Use
reviewed inputs and a supported host; there is no unsandboxed fallback. Check
outputs may contain private source or test data. No result authorizes applying
a patch. See the workbench reference for exact bounds and limitations.

## Reporting a vulnerability

Do not open a public issue for a vulnerability that could enable integrity
bypass, context-confusion, unsafe decoding, private-data exposure, or dependency
compromise.

Use GitHub's private vulnerability reporting feature for this repository when
available. If it is unavailable, use the contact address displayed on the
Titans Forge GitHub organization profile and request a private security channel.
Do not include secrets or private mission data in the initial message.

Include, when safe:

- affected commit or release;
- minimal synthetic reproduction;
- expected and observed behavior;
- security impact; and
- whether public disclosure has already occurred.

Titans Forge will acknowledge a valid private report when operationally able,
but this beta publishes no guaranteed response or remediation time.
