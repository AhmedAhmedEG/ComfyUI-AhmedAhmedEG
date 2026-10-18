# Continuity corrections in 1.7.13

Motion Context now attaches compatible previous sampled AV latent tails directly as native temporal guides. It no longer routinely decodes and re-encodes them. Decoded-tail encoding remains an explicit fallback for imported footage or a changed canvas; the run report records the path. Guide insertion preserves reference metadata and interior/closing guides, never installs global patches and never creates a target noise mask.

Audio context is independent of video context. The existing Continuity tab supports Off, 5, 22, **24**, 39 and 56 audio frames, including the original Extender's 22-video/24-audio configuration. Temporal audio is end-aligned using the signed 40-Hz/24-fps boundary remainder. Automatic promotion of previous audio to an additional standalone reference is removed; explicitly selected audio references remain active.

Latent Carry remains a mutually exclusive path using its existing tapered redraw masks and scoped model wrapper. Help text now describes that behavior rather than implying the whole prefix is frozen.

The existing Continuity tab owns one duration choice:

- **Duration = new footage** (`new`): existing workflows keep this default. The sample target grows to include the hidden prefix, then output is cropped to the requested visible length on the H3 grid. Phase alignment may trim a few frames from the predecessor at a join.
- **Duration includes context (Extender)** (`total`): sample the requested total on the H3 grid and discard its context afterward, yielding less new footage. Direct guide extraction uses the sampled latent endpoint, as in the original Extender. Converting a Tritant project selects this policy; existing Master projects are not silently migrated.

This duration option does not claim that Latent Carry is the same algorithm as Extender Motion Context.

Master output and Smart Preview now share frame-boundary PCM slicing and retain discarded audio prefixes for join blending. Assembly calculates sample counts from cumulative frame time rather than independently rounding every segment. It keeps the existing disk-backed per-clip preview/assembly architecture; no cumulative VAE re-decode or extra Master panel was introduced. Existing preview files receive a new revision key for the updated audio assembly.

## Validation

- 247 backend tests pass, including original take reuse and preview durability contracts.
- 50 real CPU numerical checks pass, including exact sampled-tail guide values, negative audio phase, source/target immutability, independent audio windows, pixel fallback, duration budgets, redraw behavior and cumulative PCM lengths.
- Editor regression verifies independent audio context and duration persistence. Four preview JavaScript suites pass.
- Runtime contracts verify no automatic standalone audio, preservation of explicit audio, guide/carry exclusivity, native guide rows reaching the sampler, total-duration output and external checkpoint handling.

These model-free results establish execution contracts, not visual seam superiority. Live GPU comparison results will be recorded after deployment. No third-party source files were changed.
