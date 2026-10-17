# Master and Smart Preview logic review — 2026-10-18

Reviewed version: 1.7.10, commit `c2fa46d1a0fd86c2112ef2d98f96d01dd7c12841`.

This review found nine reproducible issues. It changed no production code, third-party files, server settings or running workflows. No restart, deployment or GPU generation was performed for this review.

## Findings

### 1. P1 — Paired reference-video audio is dropped at the native conditioning boundary

**Code:** `nodes/node_director.py:628,644`; `core/executor.py:218`; installed native `MiniMaxH3ReferenceToVideo.execute`.

The Master builds soundtrack keys such as `ref_video_1`. The installed native consumer looks for `ref_video_audio_1`. The executor forwards the dictionary unchanged. Consequently, Video + Audio can condition on the video without conditioning on its soundtrack. Keeping source audio in the output is a separate path and can still work.

**Reproduction:** Captured the actual Master arguments and executed the installed native conditioning function body with CPU tensors and encoder spies. Original keys caused zero audio-encoder calls; changing only the key to the native spelling caused one call. This verifies the argument mismatch without loading GPU model weights.

**Suggested fix:** Normalize soundtrack names once at the executor boundary. Cover paired reference videos, multiple videos, and source-video insertion for REF2VA/V2V/RV2V using the native consumer contract.

### 2. P1 — Generation edits do not consistently invalidate approvals and downstream continuity

**Code:** `web/js/minimax_director.js:3177,3845,4396,4484,4503,4558,4572,4684,4899`; `core/timeline_input.py:17`; approved reuse in `nodes/node_director.py:500`.

The approval checkbox and LoRA changes use the chain invalidation helper. Several other generation edits clear only the edited clip's approval; raw prompt edits do not explicitly clear even that approval. The backend intentionally reuses approved takes, so these inconsistent UI mutations can preserve stale results. External Timeline Builder merging also preserves approval by stable ID even when authored generation content changes.

**Reproductions:** With two approved clips and continuity from clip 1 to clip 2, changing clip 1's seed unapproved clip 1 but left clip 2 approved. Separately, merging a changed external prompt preserved `validated: true`.

**Suggested fix:** Centralize generation-affecting change handling, including external authoring. Unmark the affected clip and dependent continuity chain, preserve cached artifacts, and record invalidated generations. Avoid invalidating harmless name or presentation changes.

### 3. P2 — The first clip cannot use the connected latent checkpoint as its predecessor

**Code:** `nodes/node_director.py:411,535`.

Checkpoint state is loaded, but continuity is gated by `clip_idx > 0`. Therefore the first clip's continuity paths cannot consume that checkpoint.

**Reproduction:** First clip I2VA with continuity enabled, a valid 22-frame checkpoint and no opening image failed with “I2V requires one opening image or a preceding clip with continuity enabled.” Sampling never started. A text-only first clip can instead silently ignore the checkpoint.

**Suggested fix:** Treat a valid connected checkpoint as an explicit external predecessor for the first clip when continuity is enabled. Validate streams and canvas compatibility and distinguish this case from trimming an actual preceding timeline clip.

### 4. P2 — Latent-only recovery can change an approved take's final pixels

**Code:** `nodes/node_director.py:429–457`, especially the import-specific grading branch at line 445.

When approved frame media is missing, recovery decodes the latent. Normal Master postprocessing is not consistently reconstructed; grading is explicitly reapplied only for the Tritant import case. A decoded latent does not inherently contain later grading or face refinement.

**Reproduction:** An approved take had graded pixel value 0.5 and latent-decoded base value 0.25. After removing its frame artifact, approved recovery returned 0.25 under the accepted take's generation identity.

**Suggested fix:** Preserve postprocessing provenance and the artifacts needed to reconstruct the accepted result. Reapply reproducible processing or report missing final media explicitly; do not silently equate an unprocessed latent decode with an immutable approved result.

### 5. P2 — Preview run freshness can hide reused drafts and conditioning-only results

**Code:** `nodes/node_director.py:380,1001,1120`; `core/cache_manager.py:238`; `core/preview.py:50–56`.

Every Master invocation begins a new preview run. Reused staged first-pass results retain their old run ID because tagging happens only when creating a new staged draft. The preview then excludes those unapproved results as stale. Conditioning Only also starts a new media freshness epoch despite not producing media.

**Reproductions:** An existing first-pass preview was available before starting a new run and unavailable after reusing the same staged draft. An actual Conditioning Only invocation similarly changed a fresh unapproved final preview from available to unavailable with zero sampling calls.

**Suggested fix:** Separate conditioning/review actions from real generation freshness. Explicitly admit reused staged results into the current run, while retaining the exclusion of old unapproved clips scheduled for regeneration.

### 6. P2 — Saved Take / First Pass selects the current draft instead of that take's draft

**Code:** `core/preview.py:25,36–39`.

The planner initially selects historical take metadata, then replaces it with the clip's current first-pass metadata when First Pass is selected.

**Reproduction:** Created draft A, final A, then draft B. Selecting saved final A with First Pass displayed draft B's generation.

**Suggested fix:** Store the first-pass generation relationship on each final take and resolve it historically. If an older take has no retained first pass, show unavailable rather than a different generation.

### 7. P2 — Restoring the preview node loses its saved processing stage

**Code:** `web/js/minimax_preview.js:176–183`.

The restore method restores scope, quality and autoplay but omits stream/stage and take selection. This matters when configuration is loaded after initial mounting.

**Reproduction:** Saved stage `pre_refine`; after calling the production player's restore method, the stage remained `final`.

**Suggested fix:** Restore all persisted options before the first refresh/persist operation and preserve valid historical take selections through configuration loading.

### 8. P2 — Saved Take playback errors claim to retry but do not automatically retry

**Code:** `web/js/minimax_preview.js:152,170`.

The media-error handler clears the logical source and displays “Retrying…”. Periodic polling explicitly skips Saved Take scope, so that view makes no automatic recovery request.

**Reproduction:** Triggered a media error in Saved Take view and executed two polling cycles: zero preview requests; status still said “Retrying…”. Manual actions or a later foreground/online event can initiate another attempt.

**Suggested fix:** Separate take-list polling from media recovery. Use bounded retry/backoff for failed playback in every scope.

### 9. P2 — A corrupt browser-cached video survives playback retries

**Code:** `web/js/minimax_preview.js:8–12,152`.

Playback failure does not evict the failed revision from memory or CacheStorage. Subsequent retries reuse the same cached blob, preventing recovery from a corrupt cache entry or a repaired server artifact at the same URL.

**Reproduction:** Simulated two decode failures and subsequent latest-preview retries: zero new media downloads.

**Suggested fix:** Evict the failed URL from both cache layers and perform a bounded network retry. Revoke unused object URLs, and keep transient metadata/API failures separate from actual media decode failures.

## Model routing

The Master does not always use REF2VA. Default routing is:

| Clip mode | Model family |
| --- | --- |
| Text to Video, Image to Video, First & Last Frame, Last Frame, Image Inpaint | FL2VA |
| Reference to Video, Video to Video, Reference Video Edit | REF2VA |
| Existing/imported video | No diffusion generation |

The supplied `MiniMax H3 Master Node(2).json` workflow contains four REF2VA clips, so it uses the REF2VA branch. Explicit connected model overrides can alter the selected model. Lazy family selection was reviewed and is not implicated in the findings above.

## Validation and limits

- Existing regression checks passed: 236 backend tests, 24 real CPU tensor/media/HTTP tests and 8 memory-retention tests: **268 Python tests total**.
- Seven JavaScript suites passed: editor, preview, preview node, preview cache, authoring tools, transfer and user guide.
- Eleven targeted reproduction cases confirmed the nine root findings above using the actual Master/editor/preview paths, CPU tensors, controlled model stand-ins and JSDOM. The native conditioning key mismatch also used the installed native function body with encoder spies.
- Green existing tests do not mean these paths are correct: the targeted cases expose missing coverage.
- Reviewed LoRA application, bounded caches and transient cleanup. This review did not establish a new memory leak or prove immunity to long GPU runs, allocator failures or CUDA crashes. It did not run a real GPU comparison or visually validate the live ComfyUI canvas.
- Reproduction details are in local ignored artifacts `.validation/master-preview-review-python-results.json` and `.validation/master-preview-review-js-results.json`.

## Recommended implementation order

1. Fix native paired-audio keys and central approval/continuity invalidation.
2. Fix first-clip checkpoint consumption and approved media recovery semantics.
3. Fix draft freshness and historical stage association.
4. Fix preview option restoration and bounded media/cache recovery.

These are fixes to the existing execution, state and preview boundaries. They require no new nodes or duplicate Master settings. This report records findings only; no production fixes have been applied as part of this review.
