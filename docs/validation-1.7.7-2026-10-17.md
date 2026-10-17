# Memory lifecycle release 1.7.7

The October 17 kernel log confirms a global host OOM kill at approximately 15:39 UTC, during clip 3 decoding. The Python process held roughly 52 GiB anonymous RSS and 12.5 GiB swap. This release changes our own execution/cache/export code; third-party plugins remain unchanged.

Per-clip finalized RGB pixels are processed in small windows into disk-backed storage before audio decoding. Completed clips retain mapped durable frames, and previous continuation state moves to CPU. Full IMAGE assembly writes bounded windows to budgeted RAM or a mapped output for large batches; it does not concatenate multiple full anonymous RGB copies. No new Master controls were added. Context values, native frame alignment and approved-take reuse remain covered by tests.

Shifted wrappers are reused within one execution with a bounded cache and strong parent identity. Owned wrappers are released through the native targeted unload API before references disappear, including error exits. Boundary cleanup collects native dead models/prefetch buffers without unloading all models into host RAM. Memory logs distinguish RSS/high-water/swap from CUDA allocation/reservation.

Project Video reuses revision-addressed encoded segments; changed media, trim/selection, canvas/FPS or audio finishing changes the cache key. Final assembly uses its existing FFmpeg stream-copy path. Smart Preview reads raw cached frames through private mappings rather than loading anonymous copies.

Local validation: 233 backend tests, 18 focused real tensor/media checks, all six JavaScript suites. Tests cover exact color/seam pixels, mixed canvas/dtype assembly, large mapped output lifetime, decoded allocation release before audio work, legacy cache loading, scope cleanup on error, bounded shifted-wrapper reuse, real MP4 repeat-export reuse and audio-setting invalidation. Runtime full-resolution validation follows deployment; its result will be appended after completion.

Full-resolution runtime result: job `4d3301b1-29eb-4282-a977-f9a5cbb203b6` succeeded in 888.74 seconds. It generated all four original ten-second REF2VA clips at 1280x736 with two steps, original prompts/seeds/assets/continuity and decoded_output=full, in an isolated project. The final mapped IMAGE output is 10,875,371,520 bytes. No production workflow or accepted take was overwritten. The test exercised the previously failing third decode and full raw assembly; it is not a twenty-step quality benchmark. Detailed memory samples were retained in the isolated project.
