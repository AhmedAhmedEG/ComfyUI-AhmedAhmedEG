# Host-memory investigation and Extender comparison

## Confirmed failure

Read-only kernel dmesg establishes a global host OOM kill on 2026-10-17 at approximately 15:39:07 UTC (18:39 Cairo). The killed ComfyUI python3 process had anon-rss 54,516,468 KiB (52.0 GiB), plus 8,072 KiB shared RSS; the process table showed 3,279,587 swapped pages (about 12.5 GiB on this 4 KiB-page host). Host RAM totals 56,555,300 KiB (53.9 GiB). An earlier kill at 12:34 UTC also appears. The entrypoint reports Killed five seconds after the kernel event, then the always-restart container restarts. This supersedes the earlier 1.7.6 report's unconfirmed termination diagnosis. It is distinct from the September CUDA allocator abort.

There is no retained per-clip RSS time series for the failed run. The kernel provides a real at-kill snapshot, not an allocation-by-allocation attribution. Docker's restarted state and reset cgroup counters did not establish the previous kill reason; kernel evidence does.

The failed run used 1280x736, four ten-second REF2VA clips, decoded_output=full, no clip LoRAs, no connected Refine/SelfLift. Clips 1 and 2 persisted 2,747,106,885 and 3,188,000,325-byte frame files. Clip 3 completed sampling, then died during decoding. The output list retained prior float32 decoded tensors despite their durable caches. Boundary cleanup only resets ComfyUI prefetch/cast buffers and cannot release live output-list references. This is demonstrated retention growth; a separate unbounded leak is not established.

## Local fixes prepared, not deployed

- Read saved RGB tensors through private memory mappings. Generated output lists switch to their durable mapped take at each completed boundary; original decoded and optional pre-refine locals are released before the next clip.
- Smart Preview maps frame files instead of allocating full anonymous copies.
- Seam matching clamps its newly owned output in place, avoiding another whole-clip allocation, with exact numerical regression coverage.
- Final assembly trims mapped clip views without cloning the whole visible clip. Full IMAGE output still requires one final assembled tensor, and mixed-size resizing can still require temporary tensors.
- Before-decode and completed-boundary logs record process RSS/high-water/swap separately from CUDA allocated/reserved memory. No UI option or third-party source changes.

231 backend tests and 13 relevant real-tensor/media tests pass. In isolated Linux CPU subprocesses, retaining eight 32 MiB clips through the old output-list method grew anonymous memory by 256.1 MiB. Mapping the same durable files and releasing the decoded allocations grew anonymous memory by approximately 0.13 MiB before access. Accessed mapped pages consume physical memory but are reclaimable from disk. These tests do not establish the peak of an actual full-resolution GPU run or guarantee it fits host RAM.

## Installed Extender comparison

The inspected snapshot under .validation/extender-2.7.4 exactly matches installed extender.py, motion_context_disk.py, and fl2va_engine.py by SHA256. The comparison covers its Ref2VA motion-context full-batch path and FL2VA checkpointing path.

- extender.py:5065-5103: samples are persisted through Disk Join; sampled, positive, latent, clip_model and clip_text_encoder references are deleted before per-clip VAE caching starts.
- motion_context_disk.py:810: video/audio latent streams append to a durable raw cache file; _LazyDiskLatent at line 912 retains a descriptor and maps streams when accessed, rather than keeping previous sampler tensors resident.
- motion_context_disk.py:3308: each Ref2VA clip is decoded and encoded into a browser checkpoint and exact-final-profile sidecar. The RGB tensor is released before AudioVAE work; cleanup also runs in finally.
- motion_context_disk.py:3193: Final Decode joins exact segment caches using FFmpeg stream copy; it need not create a whole-project float32 RGB tensor. FL2VA's cache_full_batch_fl2va_plan uses per-plan disk video/audio caches as well.

Extender therefore separates generating all clips from retaining all raw pixels. Our deployed full IMAGE-output contract is a material memory difference. The local mapping fix reduces accumulation but does not fully reproduce Extender's release-before-audio and file-only final export. Long-project delivery should use durable takes with the existing separate Project Video/export path and latest decoded Master output. Adopting further lifecycle changes belongs in the execution/cache/export implementation, not new Master controls or edits to the third-party Extender.

## AIMixer and DaSiWa optimization review

Source review uses the retained October 12 snapshots: AIMixer 8151b291fcacee5ddb70c6493eaed4f831bc6867 and DaSiWa bdb62d4c561bbed30351974844e0168ad471331a. This is source analysis, not a GPU speed comparison or a claim about subsequent upstream commits.

AIMixer:

- executor_core._prune_continuity_working_set discards older continuity AV latents, low-resolution carries and refine-pass tensors; only the predecessor remains necessary.
- With export_segments_mode active, _release_segment_pixels replaces older full-resolution outputs with one-frame posters after their MP4s and successor handoff are safe. This is conditional; ordinary all-frame output still retains chunks.
- ShiftedModelCache reuses a SigmaShift model clone keyed by parent/shift values throughout one execution, then clears it. The source explains that transient patchers can otherwise leave dead LoadedModel bookkeeping. Our vendored sampler contains this helper, but advanced_sampling creates it per call and ordinary Master sampling creates native shift clones directly. Presence of the helper is not equivalent to run-wide integration.
- vram_cleanup performs GC, native model GC, dead-slot removal, prefetch cleanup and optional global unload. Our between_clips currently performs only selected aimdo cleanup. Prefer native cleanup and correctly scoped model ownership; do not blindly copy global unload or direct mutation of ComfyUI's private loaded-model list. Global GPU offload can increase host-RAM pressure and repeated weight loading.
- File-backed reference audio is cached per execution and released after segment use; reference images have a bounded cache. Our injected pack already shares decoded assets, so adding another general reference cache would duplicate ownership.

DaSiWa:

- helper_batch_output computes required tensor bytes, reserves RAM headroom, checks free disk capacity, can allocate complete outputs with torch.from_file and registers temporary-file finalization. This solves full output allocation, beyond mapping inputs. Its helper is already vendored for output/RTX support, but Master final torch.cat does not use it.
- RTX support performs targeted device reclamation and staged native RAM-pressure cache/pin release, rechecking actual available memory; it explicitly avoids global GPU offload or resetting the running executor. These protections are already in our RTX support, not the Master's basic decode/assembly path.
- Tiled refinement plans spatial/temporal working windows with model/reference/audio/keyframe costs and workspace reserve. This is heuristic capacity planning, not a measured guarantee. Our global refinement path already invokes the adapted planner; it is not a missing new feature and it does not protect ordinary full-resolution VAE decoding.
- Local prompt-model cleanup releases weights after drafting. Our LocalProvider already implements an unload-after-draft lifetime.

Integration priorities: finish Extender-style per-clip disk lifecycle; bound the rolling working set; extend memory-aware allocation to Master full IMAGE assembly; reuse shifted patchers with execution-scoped ownership; apply pressure-based native cleanup without blanket unload. Keep export in Project Video, refinement policy in Refine, prompt-model lifetime in Local Prompt Model, and shared lifecycle helpers in core. No new Master controls or duplicate nodes are implied.
