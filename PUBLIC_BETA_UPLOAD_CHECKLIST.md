# Public Beta Upload Checklist

This checklist prepares an upload; it does not authorize one.

## Freeze

- [ ] Select the exact `main` commit for `v0.2.0-beta.1`.
- [ ] Confirm the working tree contains no unreviewed file.
- [ ] Confirm `pyproject.toml` reports `0.2.0b1`.
- [ ] Regenerate `RELEASE_MANIFEST.json` on that commit.
- [ ] Record the commit and manifest SHA-256 in the release authorization.

## Verify

- [ ] `PYTHONPATH=src python3 scripts/verify_release.py` reports `PASS`.
- [ ] Nine or more Python tests pass.
- [ ] The standalone browser codec test passes.
- [ ] Hosted macOS, Linux, and Windows CI pass on the exact commit.
- [ ] A fresh source archive installs and reproduces the shipped receipt.
- [ ] The site renders at desktop and mobile widths with the GitHub beta CTA.
- [ ] Every release-note claim appears in the public evidence packet.

## Rights and safety

- [ ] Effective MIT, patent notice, DCO, and contribution boundaries approved.
- [ ] No private data, model weights, filing documents, credentials, internal
  paths, private corpus, held test, or retired-shadow artifact is present.
- [ ] Security-reporting route is enabled on GitHub.
- [ ] GitHub issue templates and labels are available.

## Upload sequence

- [ ] Commit the reviewed beta candidate.
- [ ] Push the exact commit to `Titans-Forge-LLC/anvil`.
- [ ] Wait for hosted CI on that commit.
- [ ] Create annotated tag `v0.2.0-beta.1` only after CI passes.
- [ ] Create a GitHub prerelease from `RELEASE_NOTES_V0_2_0_BETA_1.md`.
- [ ] Mark the release as a prerelease, not latest/stable.
- [ ] Verify the public repository and release archive from a logged-out view.
- [ ] Publish promotion only after the public URLs and tester paths work.

## Rollback

- [ ] Preserve the released commit, manifest, and archive.
- [ ] If an exactness, authority, privacy, or licensing stop rule fires, mark the
  prerelease affected and halt promotion.
- [ ] Repair under a new version; never rewrite a released evidence record.

## Required operator approval

Record: exact commit, manifest hash, tag, GitHub destination, release notes,
effective license set, publication date, and the words `approved for limited
public beta publication`.
