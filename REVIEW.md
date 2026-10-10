# Consolidation review — 2026-10-09

## Node documentation site

The guide is now a static documentation site with an index, Getting Started,
and one separate HTML page for each of the 22 public nodes. Node contracts are
extracted from the actual INPUT_TYPES/RETURN_TYPES declarations in an isolated
process without loading weights. Dynamic installed-file/sampler lists are
identified rather than fabricated. Each documented input has an explanation;
all outputs, wiring examples, behavior and limits are checked against the code.
The former guide URL forwards to the index and the unused walkthrough template
is removed. Local link/anchor checks and desktop/mobile navigation checks cover
the documentation site.

## 1.0.7 visual polish

Larger controls, theme-aware surfaces, restrained violet selection, aligned
number fields and a timing grid improve the Master editor. Duplicate toolbar
shot actions are removed in favor of the inspector actions; Reset lives in
Project tools. Advanced shot sections share one row and the empty reference
pool is hidden while uploads remain available in the reference panel.

The standard starter editor fits its default prompt without inspector scrolling
at the existing node size. The actual editor DOM was visually checked, editor
and preview checks pass, and the guide screenshot is refreshed.

## Practical guide rewrite

The HTML guide follows a single six-step recipe using the actual starter values
and control names. Each diagram sits beside its instruction; no global scrolling
simulation or presentation remains. Seventeen on-demand task topics cover all
22 public tools, with model-family, continuity and latest/full preview examples.
The current Master editor screenshot is embedded in the standalone offline HTML.
Guide interaction checks pass; desktop and 390-pixel mobile layout were visually
checked with no horizontal overflow.

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

## Timeline interaction repair (1.0.8)

Shot bodies now drag to reorder the complete shot and its reference lanes, with an insertion marker and graph-zoom-aware motion. The right edge resizes duration. Every shot has Delete, including the last shot; intentionally empty timelines persist and execution reports Add Shot instead of creating a fallback. Move earlier/later buttons preserve keyboard access. Locked source clips stay in place, and affected successors lose approval after ordering changes. Verified in a browser and the editor regression harness; 103 Python tests pass.

## Beginner documentation and drag recovery (1.0.9)

Getting Started now explains nodes, sockets, cables, model files, all nine starter boxes and common generation terms. All 22 node pages include a plain-language explanation and first-use example. Real screenshots were captured from the installed ComfyUI frontend running the supplied starter in an isolated read-only preview, including readable model, VAE and settings close-ups. No generation or remote workflow changes were made.

Shot dragging now captures the pointer and handles movement/release before canvas listeners, cancels on leaving the editor, losing capture or losing window focus, and clears transforms during rerenders. Actual ComfyUI browser checks confirmed reordering and outside-node cancellation; regression tests cover outside movement and blur without lost clips.

## Smart-preview starter (1.0.10)

The starter now ends at the Master's integrated Smart Preview, opens Latest clip with autoplay, and omits Create Video / Save Video. The Master is an output node so generation runs without an export sink. The consolidated workflow retains final export. Workflow import now restores the preview panel, scope and autoplay instead of only loading the saved options. Regression coverage verifies runnable output registration, absence of starter savers, valid links and restored player settings.

## Separate preview and pool-only authoring (1.1.0)

Smart Preview is now a separate output node connected to Master project_state. Master has no integrated player or preview/output selector. Settings presents one Generation mode and removes prompt/preview controls. Raw/Structured remains per shot. Reference discovery includes only connected pool slots or nonempty RefMods; named references retain stable IDs, and prompt tokens appear only for assigned media. New reference uploads and manual file inputs are removed from Master; source selection is from the pool, with legacy project compatibility. Reference observers support multiple Masters and clean up when removed. Image thumbnails use larger contained previews and click-to-expand, and empty tracks are hidden. Timeline widths follow duration.

Starter and consolidated graphs include both H3 SLA Attention patches and the existing stock REF2VA Turbo LoRA/Boolean/model switch, using the supplied workflow and schemas read from the installed remote nodes. The user still sets the intended 8-step sampling value when enabling the supplied LoRA. Backend: 108 tests pass, including protection against treating the hidden ComfyUI execution graph as user prompt text. Editor, preview, separate-player and documentation regressions pass. Updated screenshots show the actual 14-node starter and simplified controls.

## Compact timeline and automatic Turbo steps (1.1.1)

The prompt editor no longer stretches to fill the node. Shot cards start at a readable scale, include assigned image covers and show multiline prompt snippets. The starter flows left to right in topological order. A single Boolean selects both the REF2VA base/Turbo branch and 25/8 sampling steps through stock, collapsed model and integer selectors. Director Settings steps is a connected input. Both examples validate against the installed server. 109 backend tests and editor/preview/docs checks pass. A fresh native frontend renders Generation mode above Continuity mode; the reported missing control remains under investigation for saved or stale node definitions.

## Technical documentation and control audit (1.1.2)

Added authored technical chapters for all 23 public nodes and an architecture chapter, with execution contracts, temporal/spatial math, cache/state lifecycles, practical examples, dependencies and provider-specific limitations. Schema tables remain a quick reference after the technical explanation. Offline links, anchors, navigation and rendered layout were checked.

Fixed Settings migration for named legacy arrays and current arrays missing the seed control; group reference sizing previously ignored by conditioning; graph-only group tensors leaking into autosave/project JSON; pool-only original-canvas discovery; a removed upload-control variable breaking the locked-source inspector; locked-source edge resizing; and Prompt Forge pool metadata/context invalidation. Runtime and editor regressions cover these defects. All 114 backend tests pass. Generation mode is declared as an ordinary visible combo and appears in a fresh native frontend; the precise cause of the user screenshot missing it is not established.

## Ruler and playhead alignment (1.1.3)

The ruler fills the timeline horizon and ends at a labeled whole interval, including empty space after the final shot. Clips and scrubbing share its time scale. The playhead origin follows the rendered header width rather than the obsolete 130px offset; it reaches zero and the entire visible ruler remains scrubbable. Regression coverage verifies zero, interval endpoint, empty-space scrubbing and 155% graph zoom.

## Discoverable panels and per-shot continuity (1.2.0)

Replaced inline advanced controls with full-width bordered expandable sections, labeled fields, help text and grid alignment. Project tools, Prompt Forge, RefMods, shot model/anchor/grading and LoRA controls are discoverable through prominent headers; the editor scrolls vertically instead of clipping expanded tools. Generation mode is now an explicit Master toolbar control; Settings contains sampling/canvas only. Saved workflow migration moves the former global controls into connected Master state.

Continuity method and video/audio frame contexts are per shot. Audio may be disabled independently and is capped to usable video context; latent carry also receives the selected audio pin/count and seam redraw. Timeline overlays show planned context borrowing, capped to authored predecessor availability; native frame rounding can change actual availability. Completed/cached shots retain the maximum supported 56-frame tail so successors choose their own context. Settings/starter schemas, manual sections and tests were updated. 118 backend tests and editor/preview/docs checks pass; no GPU generation was performed.


## 1.3.0 — one configuration owner and timeline video continuation

- Removed embedded Prompt Forge/RefMod configuration and exporter/checkpoint creation actions from the Master. External nodes retain their algorithms and APIs.
- Moved canvas policy to Settings; saved UI timelines migrate previous canvas policies into connected Settings. Updated both example workflows and Settings sizing.
- Master toolbar imports existing video as a locked source clip. Generated clips accept an explicit continuation video in their Continuity section; only the last 56 frames worth is decoded, and source context is excluded from output. External Latent Carry never trims unrelated predecessor output. Portable projects include continuation files.
- Mode-specific reference rows/tokens match backend consumption; T2V ignores inactive assignments and keyframe modes ignore non-image assignments. Pool RefMods are consumed only by assigned reference-mode clips.
- Bordered timeline, clip terminology and described Files & recovery cards replace ambiguous unlabeled project actions. Separate Smart Preview remains the starter output.
- Removed premature model validation that blocked timeline Conditioning only and source passthrough; generated clips still validate their required family model.
- Validation: 124 backend tests, editor interaction/migration/file-continuation checks, both preview suites, offline documentation links and workflow contracts pass. Real installed frontend inspected through an isolated read-only proxy. New video continuation sampling has mock pipeline coverage; GPU quality has not been benchmarked.


## 1.4.0 — timeline editing workspace

- Split the inspector into a primary writing area and a bounded tool panel. Prompt, duration, seed and audio do not move when advanced panels change.
- Added Continuity, Look, LoRAs and Project tabs with keyboard navigation, ARIA state and independent scrolling. The toolbar opens the same Project configuration surface.
- Increased control/text sizing and contrast, simplified surfaces, aligned controls and introduced a restrained blue accent for selection.
- Optional Help reveals longer explanations while control labels stay visible. Video continuation is the first field in its tab. Clip approval is now a keyboard-accessible button.
- Updated beginner instructions that still pointed to Generation mode in Settings; rebuilt the per-node documentation and actual frontend captures.
- Editor interactions, ordering/resize/drag cancellation, file continuation, serialization, language, tool navigation and single ownership checks pass. Preview suites, 124 backend regression tests and documentation/workflow contract checks pass.

## 1.4.1 — toolbar ownership

Removed the duplicate Project shortcut. Consolidated JSON and portable archive imports into one action and exports into one action with an Include media option in Project / Files & recovery. Moved the selected-clip eligibility filter beside Generation mode and upstream refresh beside the reference pool. Timeline navigation is a bordered strip with footage insertion, totals, timecode, zoom and language. No backend generation semantics changed. Editor regressions cover ownership and both export routes.
