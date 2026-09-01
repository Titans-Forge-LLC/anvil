# Claims and Limitations

## Public reference claims

The AVP1 reference profile may be described as:

- deterministic for supported JSON values;
- exactly reversible on its conformance tests;
- explicitly bound to a named context profile;
- fail-closed when decoded under the wrong profile;
- authority-preserving when the authority manifest is part of the source
  semantic object;
- offline and incapable of executing mission operations.

These claims must be accompanied by the tested version or release manifest.

## Historical AVD2 claim

The following sentence is the approved bounded form:

> AVD2 encoded 14,708 canonical semantic bytes into 3,143 wire bytes, a 4.6796x
> byte-compression ratio, on one frozen 31-directive historical Forge cohort;
> all 180 semantic and authority fields reconstructed exactly.

## Unsupported claims

Do not claim that:

- ANVIL universally compresses by 4.6796x;
- AVP1 reproduces the AVD2 result;
- ANVIL reduces model costs or training time by a fixed factor;
- exactness on registered cases is formal verification;
- zero observed authority failures is a general security guarantee;
- ANVIL is deployed in the live Forge;
- ANVIL has passed prospective qualification;
- the public reference profile proves patent novelty.

## Current research status

The prospective Forge collector remains separate from this package and does not
gate release of a clearly labeled limited public beta. Production qualification is a
later, stricter gate.
