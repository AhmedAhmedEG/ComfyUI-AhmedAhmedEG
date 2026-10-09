# Consolidation review — 2026-10-09

## 1.0.6 editor and smart preview

The timeline ruler now uses DOM text and ticks instead of a stretched canvas
bitmap. Scrubbing converts screen coordinates to graph coordinates, including
155% zoom. The editor inherits ComfyUI theme colors and removes nested outer
borders. A Preview tab uses the existing node area rather than inflating its size.

The preview player restores completed takes, follows newly finished shots,
supports autoplay and saving, and defaults to Latest clip. Explicit Full video
mode assembles completed caches and locked source ranges. Independent immutable
preview revisions prevent whole-sequence buffering in Latest mode. Encoding is
lazy and uses the existing PyAV H.264/AAC encoder, with HTTP byte-range delivery.
Preview files fit within 960 × 540; final exports are unaffected. No sampling or
VAE decode is added. A missing cache reports that no clip is available instead
of silently falling back to a complete video.

Validation: 102 regression tests, 20 real CPU/media tests, editor, preview and
guide checks. Tiny encoded media verifies that Latest loads only the newest shot,
Full respects seam trimming, and old preview revisions survive rerenders. Player
checks cover stable URLs, autoplay, saving and late-response cleanup. GPU
sampling was not run.

## 1.0.5 public-node audit

Removed eight redundant public types: diffusion/encoder loaders and VIDEO
adapter (stock equivalents); Sampling Settings (subset of Director Settings);
Reference Bridge (covered by the chainable reference pool); two guide wrappers
whose MINIMAX_H3_DIRECTOR_GUIDE input has no producer in this pack. Prompt Bridge is replaced by a direct STRING prompt_text input. Their files,
classes, imports, mappings and guide entries are removed. There are 22 public
nodes, one Master. Existing saved graphs using removed types need replacement
nodes; the fresh starter avoids them entirely.

Retained enhancement configs, continuity/take checkpoints, prompt drafting,
RefMod pools, per-shot models, external shot groups, tail extraction and project
export because their typed graph integrations and timeline behavior have no
stock equivalent. Retained advanced video export for H.265/VP9, bitrate/audio
options, metadata, crop-to-audio and still extraction; basic output now uses
stock Create Video / Save Video. Playback/watermark/loop processing and Pixel/
RTX refinement operate on frame batches and provide additional pipeline features.

Both examples include native FL2VA and REF2VA loaders, CLIP and two VAEs. Master
provenance follows directly connected native loaders using hidden PROMPT data;
unknown modifier paths use live-object identities instead of guessed provenance.
Editor DOM positioning uses the socket offset consistently, and workflow group
bounds include full node heights. Nodes occupy separate columns with gaps.

Validation: 102 regression tests, 14 CPU/media tests, editor and guide checks
pass. The nine-node starter validates against the remote server’s native
schemas with no graph-health warnings. The editor DOM was visually checked
for containment and themed controls; full canvas startup in the isolated
preview was unavailable. No GPU generation was run for this refactor.

## 1.0.4 workflow import repair

The Settings workflow omitted ComfyUI's extra `control_after_generate` widget
after `seed`; this shifted subsequent execution/prompt/continuity fields.
Both examples now include the seed control and named widget values. The editor
migrates older Settings arrays and the previous exporter's array without its
new backend field. Named serialization/restoration prevents later field additions
from shifting values. Regression checks cover widget types/order, socket links,
unique public names, preserved booleans, nonserialized UI widgets, and layout.

`MiniMax H3 Start Here.json` uses five everyday nodes and one FL2VA loader.
The consolidated example keeps REF2VA and a muted cached exporter; that exporter
now sits below Video Combine rather than overlapping it. The offline animated
guide downloads the simple starter. `/minimax_director/status` identifies the
version and path loaded by the running process; pulling Git files alone does
not reload its Python definitions.

The reported screenshots match the pre-consolidation definitions: duplicate
Master aliases, absent loaders/Project Video, and no exporter backend widget.
This supports a running-definition mismatch, but the remote API timed out, so
the server process and installation path have not been directly verified.

ComfyUI automatically adds a workflow seed-control widget, as shown in its
[integer widget implementation](https://github.com/Comfy-Org/ComfyUI_frontend/blob/main/src/renderer/extensions/vueNodes/widgets/composables/useIntWidget.ts).
Validation for 1.0.4: 99 regression tests and 14 real CPU/media tests pass in
the validation environment, plus the editor and animated-guide JavaScript checks.

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
and clean themselves up. The package originally contained 30 distinct public nodes, one Master
name, the current workflow, notices, tests and a reproducible release builder.

Source-reference clones, scratch scripts and stale release ZIPs are development
artifacts, excluded from Git and the package. The workflow is now tracked; the
former blanket JSON/workflow ignore rules have been removed.
