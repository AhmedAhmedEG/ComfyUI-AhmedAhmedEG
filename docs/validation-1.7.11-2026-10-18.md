# Master and preview repairs — 1.7.11

This release addresses the nine findings in `master-preview-review-2026-10-18.md` within existing nodes. It adds no nodes or Master controls and changes no third-party source.

- Normalize paired reference-video soundtrack keys at the native executor boundary.
- Centralize editor approval invalidation for generation-affecting edits, including dependent continuity clips. Runtime seed advancement preserves approval. External authored prompt/content changes also reject old approvals; unchanged authored groups retain them.
- Let the first chained clip consume an explicitly connected checkpoint without trimming a nonexistent timeline predecessor.
- Persist recovery color settings and final-media requirements. Latent recovery uses the accepted take's saved color settings. Missing seam-graded/face-refined final frames, or older takes without recovery provenance, require restoring final media or explicitly unapproving; they cannot silently become different accepted pixels.
- Keep Conditioning Only from starting a media freshness epoch. Explicitly reused staged drafts become reviewable in the new run without copying tensors.
- Associate historical first-pass metadata with its completed take. Older takes without this association report that stage unavailable instead of displaying another draft.
- Restore preview stage and saved-take selection when loading node configuration.
- Retry Saved Take playback failures with bounded backoff. After three automatic retries, show an explicit Refresh action.
- Evict failed media from memory and persistent browser caches and bypass HTTP cache on the next media fetch.

Local validation: 243 backend tests and 32 real CPU media/HTTP/memory tests passed; eight JavaScript suites passed, including new regressions for approval chains, historical stage restoration, bounded retries and persistent/HTTP cache recovery. Targeted Master tests cover paired soundtrack slots, checkpoints, conditioning freshness, draft reuse/history and immutable accepted-media recovery.

Local test models use controlled stand-ins; the live tests below separately exercised real GPU generation.

## Persistent clip and player state

The timeline now displays a server-derived Saved badge when a generated latent is present on disk. This is independent of approval. Invalidated or currently replaced latents are labeled Previous. Cache status is fetched again after loading the editor, so these indicators survive browser reloads.

Preview scope, quality, stage, historical take selection and autoplay preferences are stored in node properties and browser local storage, scoped to the project and preview node. More recent browser preferences survive restarting with an older saved workflow. Playback positions are bounded to eight media revisions and flushed when leaving the page. A regenerated revision gets its own position and buffered media. Storage-denied browsers continue with workflow properties and ordinary playback; browser storage is best effort.

A regression creates a fresh JSDOM browser context with no session cache or node properties and verifies preference/take/stage restoration, playback resume and replacement media after a revision changes. This is browser-harness verification, not a claim of visually inspecting the user's live canvas.

## Live deployment and generation

- The container loaded 1.7.11 after the authorized restart. Public node count remained 27.
- Real all-clips run `d1dc6234-3e8b-41dd-83a3-3e0ba083e586` completed all four REF2VA clips successfully. Test settings: 320×192, two steps, requested two seconds per clip; H3 temporal alignment produced 56 frames per clip (2.333 seconds at 24 fps).
- The run used isolated project `validation_1711_1792273409`, preserving the original `first_video` takes and workflow. The completed test was saved in the server project list as **Validation 1.7.11 - Completed four clips**.
- All four clips reported saved frames, audio and latents and were eligible for approval.
- All 16 real clip progress events were replayed through the production editor. Only the active clip was highlighted, and completion cleared its highlight. Loading actual server cache status restored four Saved indicators after editor reload.
- Both Latest and Full served MP4 range responses (206). With two completed test clips, Latest contained clip 2 only: 56 frames / 2.333 seconds; Full contained clips 1–2: 112 frames / 4.667 seconds. Final plans selected clip 4 for Latest and all four clips for Full.
- The original project's apparently blank Latest selection was independently checked: its server-selected clip 2 served a valid MP4, 243 frames / 10.125 seconds at 1280×736. Its Full preview contained only its two completed takes: 486 frames / 20.25 seconds. The isolated four-clip test does not overwrite or add takes to that original project.
- A separate real FL2VA text-to-video run `61f0f214-adfa-4cf9-853e-14030d656260` completed successfully at 320×192, one step, requested two seconds. The alternate model branch is exercised, not merely inferred from routing code.

- Regeneration run `0e96b648-d9f1-4e2e-b334-2c76005cef0b` completed successfully with the first three clips approved and only clip 4 regenerated (one step). The first three generation IDs were unchanged; clip 4 received a new ID. Latest selected that new clip 4; Full still contained all four and received a new revision key. Both new MP4 revisions served valid range responses. The saved isolated test project was updated to this final state.
- Browser-durability and Saved-indicator changes are frontend-only and require no additional server restart. The complete eight-suite JavaScript check passed after these additions.

The real GPU runs did not crash, but these reduced-size smoke tests are not a guarantee for every resolution, model, attention backend or long-running workload. No third-party patch was applied.
