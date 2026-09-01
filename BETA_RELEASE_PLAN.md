# ANVIL Limited Public Beta Plan

Status: `PREPARED / NOT PUBLISHED / PUBLICATION NOT AUTHORIZED`

## Release shape

The first public step should be a source-only GitHub beta, not a package-registry
or production-runtime launch.

- Proposed tag: `v0.2.0-beta.1`
- Proposed channel: GitHub source release from one frozen revision
- Audience: developers and researchers willing to run the conformance protocol
- Support posture: best-effort research beta
- Distribution excluded: PyPI, npm, container registries, hosted APIs, live
  Forge integration, and production binaries

The beta is public in availability but limited in scope and claims. It exposes
the AVP1 reference profile and testing framework; it does not expose private
experimental corpora, trained models, private evidence, filing documents, or
the future Community Engine implementation.

## Beta objectives

1. Obtain clean independent reproduction across at least three outside
   environments.
2. Collect at least 25 independently authored public or synthetic messages.
3. Find portability, schema, documentation, corruption-handling, and usability
   failures before a broader release.
4. Measure exact byte outcomes without presenting them as model-speed results.
5. Validate that the contribution and issue process is understandable.

## Entry gates

Before the beta is published, all of the following must be true:

- the exact release manifest reports `PASS` with no unexpected files;
- Python and browser conformance tests pass on the exact revision;
- hosted CI passes on macOS, Linux, and Windows;
- the effective license, patent notice, and contribution terms are approved for
  that exact file set;
- the public evidence packet contains no private-only learned claim;
- an explicit operator approval records the revision, tag, destination, release
  notes, and publication date.

An outside reproduction is a beta objective rather than a prerequisite for the
first source-only beta. It remains a prerequisite for removing the beta label.

## Exit gates for broader release

- at least three independent clean-clone receipts from at least two operating
  system families;
- zero unresolved semantic or authority exactness failures;
- zero uncounted repairs or fail-open corruptions;
- every reported negative retained with its resolution or documented boundary;
- at least 25 independently authored public or synthetic test messages;
- no unresolved critical or high-severity security report;
- final evidence, license, documentation, and reproducible archive reviewed on
  the exact release candidate.

## Stop and rollback rules

Pause additional promotion and mark the beta affected if any tester reports:

- semantic or authority mismatch after a successful decode;
- wrong-context or corrupt input accepted as valid;
- nondeterministic wire output for an identical registered input;
- private data, secret, internal path, or excluded artifact in the release;
- materially misleading public claims or an effective-license mismatch.

Preserve the affected revision and receipt. Do not rewrite the evidence. Repair
under a new beta version and publish a clear advisory only after operator
approval.

## Claim boundary

The beta may be described as an exact, reversible, compact reference protocol
and experimental AI-native representation. The public AVP1 fixture currently
shows a `1.2957x` byte ratio against canonical JSON. Private learned evidence,
whole-model compute measurements, reasoning hypotheses, and prospective Forge
results are excluded unless separately selected and published with their full
evidence and limitations.

This plan does not authorize a commit, push, tag, release, deployment, or public
announcement.
