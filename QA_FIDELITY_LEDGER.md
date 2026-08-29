# Public Alpha Site QA and Fidelity Ledger

Status: `PASS / LOCAL RELEASE CANDIDATE`

## Design reference

The accepted visual system is the existing private campaign preview at
`../campaign/site/index.html`, especially its restrained paper/carbon palette,
monospace ANVIL wordmark, serif thesis line, evidence instrumentation, sparse
status color, and open section rhythm.

The public alpha intentionally replaces the private page's historical-only hero
with an AVP1 reference-profile instrument and moves the historical AVD2 metrics
below the working demo. This is a functional extension inside the accepted
design system, not a visual redesign.

## Render method

`scripts/render_site.mjs` uses the bundled Playwright Chromium runtime to load
the page through its actual `file://` usage path, capture desktop and mobile
screenshots, and exercise the wrong-context and reset interactions.

## Comparison ledger

| Area | Private concept evidence | Public render evidence | Result |
| --- | --- | --- | --- |
| First-view hierarchy | Large ANVIL wordmark and serif thesis dominate | Same hierarchy and responsive ordering | Pass |
| Palette | Paper background, carbon text, cyan/green/amber status | Same restrained tokens without added gradients or imagery | Pass |
| Typography | Monospace system UI plus editorial serif display | Same division across navigation, instrumentation, and thesis copy | Pass |
| Container model | Open bands, rails, and one technical instrument | Demo uses one workbench plus open evidence and boundary bands | Pass |
| Claims | Bounded AVD2 evidence beside exactness limits | AVD2 stays bounded and AVP1 is explicitly separated | Pass |
| Interaction | Private claim-boundary disclosure | Public encode, wrong-context refusal, and reset paths work | Pass |
| Mobile | Single-column hierarchy with readable evidence | 390 x 844 first view is unclipped and legible | Pass |

## Above-the-fold copy diff

Intentional replacements:

- `Private preview` -> `Local release candidate`
- historical AVD2 invariant panel -> synthetic AVP1 reference-profile panel
- old expanded name -> filed canonical name
- static proof command -> working exact-round-trip command

No unapproved performance, availability, support, pricing, or production claim
was added.

## Interaction evidence

- Browser AVP1 wire equals the standalone JavaScript reference wire exactly.
- Wrong profile returns a visible profile-mismatch refusal.
- Reset restores an exact semantic and authority round trip.
- Python and JavaScript conformance tests pass independently.

## Remaining intentional boundary

The site says `Local release candidate` and `Publication not yet authorized`.
Repository, download, and commercial calls to action remain absent until the
license and operator publication gates are satisfied.
