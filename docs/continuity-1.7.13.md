# Continuity corrections in 1.7.13

Motion Context now attaches compatible previous sampled AV latent tails directly as native temporal guides. It no longer routinely decodes and re-encodes them. Decoded-tail encoding remains an explicit fallback for imported footage or a changed canvas; the run report records the path. Guide insertion preserves reference metadata and interior/closing guides, never installs global patches and never creates a target noise mask.

Audio context is independent of video context. The existing Continuity tab supports Off, 5, 22, **24**, 39 and 56 audio frames, including the original Extender's 22-video/24-audio configuration. Temporal audio is end-aligned using the signed 40-Hz/24-fps boundary remainder, quantizing its guide end before deriving the start, as in Extender. Automatic promotion of previous audio to an additional standalone reference is removed; explicitly selected audio references remain active.

Latent Carry remains a mutually exclusive path using its existing tapered redraw masks and scoped model wrapper. Help text now describes that behavior rather than implying the whole prefix is frozen.

The existing Continuity tab owns one duration choice:

- **Duration = new footage** (`new`): existing workflows keep this default. The sample target grows to include the hidden prefix, then output is cropped to the requested visible length on the H3 grid. Phase alignment may trim a few frames from the predecessor at a join.
- **Duration includes context (Extender)** (`total`): sample the requested total on the H3 grid and discard its context afterward, yielding less new footage. Direct guide extraction uses the sampled latent endpoint, as in the original Extender. Converting a Tritant project selects this policy; existing Master projects are not silently migrated.

This duration option does not claim that Latent Carry is the same algorithm as Extender Motion Context.

Master output and Smart Preview now share frame-boundary PCM slicing and retain discarded audio prefixes for join blending. Assembly calculates sample counts from cumulative frame time rather than independently rounding every segment. It keeps the existing disk-backed per-clip preview/assembly architecture; no cumulative VAE re-decode or extra Master panel was introduced. Existing preview files receive a new revision key for the updated audio assembly.

## Validation

- 248 backend tests pass, including original take reuse and preview durability contracts.
- 50 real CPU numerical checks pass, including exact sampled-tail guide values, negative audio phase, source/target immutability, independent audio windows, pixel fallback, duration budgets, redraw behavior and cumulative PCM lengths.
- Editor regression verifies independent audio context and duration persistence. Four preview JavaScript suites pass.
- Runtime contracts verify no automatic standalone audio, preservation of explicit audio, guide/carry exclusivity, native guide rows reaching the sampler, total-duration output and external checkpoint handling. Actual native guide contents also participate in the staged-take fingerprint, so changing a parent latent requires a fresh first-pass review even when its prompt and seed match.

## Live GPU and preview verification

Deployed and loaded 1.7.13 at `faf2299` with 27 public nodes. The queue was idle before each reload. No third-party source files were changed.

At 320×192, two Euler/simple steps, fixed seeds and the four connected image references:

- Initial All clips run completed four clips: independent, Motion Context with Extender duration, Motion Context with new-footage duration, then Latent Carry. Sampling/completion events advanced through clips 1–4 in order.
- Final corrected-code run reused the approved first clip without sampling and generated clips 2–4 successfully. Both motion clips reported `sampled_latent`; the carry clip reported `latent_carry`. No cache errors or CUDA errors occurred. Full output: 197 frames at 24 fps.
- Matched comparison used the installed **MiniMaxH3MotionContextRAM** node, the exact same clip-1 AV checkpoint, seed 222, ordered references, fresh 56-frame target, model, shifts and sampler schedule. Both sampled streams matched the corrected Master's Extender-duration Motion Context output **bit for bit**: video `[1,24,17,12,20]`, audio `[1,32,2,93]`; maximum and mean absolute differences were zero. This checks continuity execution for this small case, not the whole original Extender engine or visual quality at production resolution.
- Full preview encoded all four clips: 197 frames / 8.2083 s. Latest encoded 56 visible frames / 2.3333 s. Historical Saved take encoded the earlier clip-2 version: 34 visible frames / 1.4167 s. Each carried stereo 48 kHz audio with matching duration to MP4 timestamp precision.
- Fourteen additional real preview/media codec tests passed. Total unique Python checks across the backend, numerical and preview/media suites: **312**, plus the editor and four preview JavaScript suites.
- Memory/progress snapshots were retained during both short runs. There was no OOM/crash, but these are not long-chain peak-memory benchmarks and do not establish absence of every possible leak.

Evidence remains in `.validation/continuity1713-{history,events,stats}.json`, `.validation/continuity1713-final-{history,events,stats,report}.json`, `.validation/continuity1713-original-history.json`, `.validation/continuity1713-gpu-comparison.json` and `.validation/continuity1713-preview-results.json`. All temporary test/remote helper processes exit after collection. The user's `first_video` project, workflow and existing takes were not changed.
