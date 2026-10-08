# Consolidation review — 2026-10-09

This 1.0.3 review supersedes the earlier 1.0.1 report. The earlier description of
Image Inpaint, rejection of source V2V/RV2V parity, approximate SelfLift, independent
whole-tile sampling, and heuristic face refinement no longer describes the default
Director. The required feature union remains in FEATURE_PARITY.md.

## Implementation choices and repairs

| Subsystem | Consolidated choice / important repair |
| --- | --- |
| Native conditioning | Native H3 task/guide APIs, modern NodeOutput handling, paired video soundtrack ordering, CFG payload preservation |
| Timeline | Source-bound V2V/RV2V, exact ranges, locked Clip 0, selection/cache/source passthrough, shared/local refs and prompts |
| SelfLift | Selected AIMixer Euler-state lift, spatial conditioning transforms, pixel/rho/transition controls and low carry; obsolete approximation removed |
| Continuity | Native guides or phase-aware AV latent carry, model-scoped schedule remask, exact visible-range and seam trim persisted for disk export |
| Refinement | Selected DaSiWa shared-trajectory spatial tiling and aligned temporal planner, original audio, custom schedules/models/passes, learned precision and endpoint/continuation repin |
| Learned upscale | Exact 24-channel 3D architecture detection, strict shapes/keys, normalization, bounded ownership, safe relative paths and weights-only loading |
| Face refine | Selected track/inject/stitch, native joint-AV sampling, explicit no-face result, zero blend/color/feather values respected; obsolete heuristic API removed |
| Authoring assets | Guarded content-addressed upload, real waveforms and trims, draggable crop, non-destructive edits, LoRA metadata, RefMod member identity |
| Prompt Forge | Local/Ollama/compatible providers, optional vision, editable reviewed shots, source context hash, whitelist preventing asset/validation injection |
| Persistence | Atomic artifact generations, previous take survives failed writes, recursive CPU/nested mask and low-carry serialization, safe imports, stable supplied-loader provenance |
| Output | Real VIDEO adapter, cached shot-by-shot disk assembly, pre-refine/original source streams, actual 10-bit PyAV, explicit audio codecs, metadata and guarded preview transcode |
| Frontend | Imported unnamed-shot crash fixed, uploaded refs survive graph disconnection, uint64 text seeds, completed-shot advancement, language switch, explicit draft apply, listener cleanup |

## Verified locally

- 96 regression tests pass using real CPU PyTorch preloaded and mock native
  ComfyUI nodes. They cover modes, conditioning, audio/time, cache invalidation,
  projects, references and error contracts.
- 14 additional CPU numerical/media tests pass: per-step tile trajectory and
  state cleanup, Euler transition, learned architecture, nested serialization,
  loop/FPS audio timing, watermark/waveform, zero-blend face stitch, continuity
  mask/repin, actual 10-bit MP4/AAC and metadata, trimmed media decoding, and FLAC
  codec retention.
- The mounted DOM scenario verifies editor startup with imported unnamed shots,
  uploaded-ref retention, exact maximum uint64 seed, English/Arabic switching
  without changing user text, draft edit/apply and event listener cleanup.
- Python parsing, JavaScript module syntax, workflow links and archive contents
  are checked when building the release.

## Remaining validation limits

No real H3 weights/GPU sampling, detector inference, large learned-upscale
checkpoint, local LLM weights, or RTX SDK were available locally. Numerical tests
use small tensors; they are not a VRAM/performance/quality benchmark. ComfyUI's
native source was inspected, but the installed remote instance was not tested.
Remote access was left aside at the user's request; no deployment or remote
generation was performed. Credentials are excluded from source and the release.

Direct selected DaSiWa code makes the combined distribution GPL-3.0, with
upstream Apache/MIT provenance retained. The vendor code does not register its
own competing Directors, frontend extensions, or routes. Unused global context-patch implementations have been removed.

## 1.0.3 cleanup

Removed obsolete approximate SelfLift, heuristic face refinement, global motion
patches, unused copied vendor algorithms/pack reports/preview routes, redundant
media/prompt helpers, the unloaded duplicate stylesheet, and the outdated workflow.
The current tracked-face and shared-trajectory implementations are retained.
Tests of removed paths were replaced by native phase, tracked-face and actual
editor source-splitting checks. Regression caches now use temporary directories
and clean themselves up. The package contains 30 distinct public nodes, one Master
name, the current workflow, notices, tests and a reproducible release builder.

Source-reference clones, scratch scripts and stale release ZIPs are development
artifacts, excluded from Git and the package. The workflow is now tracked; the
former blanket JSON/workflow ignore rules have been removed.
