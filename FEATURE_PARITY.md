# Required feature union and implementation decisions

## Product requirement

This project must consolidate the MiniMax H3 authoring, generation, continuation,
conditioning, refinement, reference, caching, and export capabilities from all
three source projects. Missing functionality is unfinished required work, not a
reason to narrow the product. Existing working features must remain available.

For overlapping features, choose the strongest implementation per subsystem,
using native compatibility, correctness, recoverability, memory use, output
quality, and integration complexity. Prefer direct native APIs over unnecessary
global patches. Performance/quality comparisons need actual GPU measurements;
the decisions below are engineering choices based on source inspection, not
benchmarked claims.

The consolidation concerns the MiniMax/video production pipeline. DaSiWa also
contains unrelated general-purpose nodes; their presence does not make them
MiniMax features. Relevant supporting features such as scaling, LoRA control,
prompt assistance, watermarking, and video export are included below.

## Pinned reference sources

Compared against pinned upstream checkouts on 2026-10-08. The temporary checkouts
were removed after review; selected implementations and licenses live in
`core/vendor/`. The source plugins are not loaded as additional ComfyUI plugins.

| Source | Revision | Main evidence |
| --- | --- | --- |
| [DaSiWa](https://github.com/darksidewalker/ComfyUI-DaSiWa-Nodes) | `aedf3592e57650494f68b4c8fb7f45edc25ca933` | `docs/minimax_h3_director.md`, `docs/h3_continuity.md`, `docs/minimax_h3_tiled_upscale.md`, corresponding `nodes/` and `js/` implementations |
| [AIMixer](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director) | `a8f57b8e23c46ee28fdb96796510fa7b4f3b1fbb` | `README_EN.md`, `director/`, `lib/`, `nodes/`, `web/js/` |
| [Tritant](https://github.com/tritant/ComfyUI_MiniMax_H3_Extender) | `1cf9bb966c2692359ac843c196454ba436ee1201` | `README.md`, `extender.py`, `fl2va_engine.py`, `latent_refine_engine.py`, `web/` |

Status vocabulary: **present** means an execution path exists; **partial** means
important source capabilities are missing; **missing** means no complete path
exists. Present does not imply real GPU validation. All rows now have local implementation paths. Real ComfyUI GPU validation is
still pending; the local suites cannot prove optional-model quality or runtime
performance. Implementation and deployment validation are separate statuses.

## Feature inventory

| Required capability | Source(s) | Current status | Chosen direction / acceptance criterion |
| --- | --- | --- | --- |
| T2VA / I2VA / FL2VA / L2VA | D, A, T | present | Native endpoint routing with DaSiWa's task validation; preserve explicit closing-only input |
| REF2VA images/video/audio | D, A, T | present | Native reference node, ordered labels, correct paired soundtrack payloads |
| Source V2V/RV2V timeline | A | present | AIMixer-style source ranges bound to Video 1, with additional refs and source preview |
| Image Inpaint / single-image mode | D | present | One image into a native five-frame pass; expose a generated still. This upstream feature is not a mask editor |
| Per-shot duration, prompts, seeds | A, T | present | One canonical shot schema; full 64-bit seeds must survive JSON/UI round trips |
| Generation/source timeline editing | A, T | present | One timeline handling both generated shots and original source ranges |
| Split/equal-split/merge/remove boundaries | A | present | Source-range operations that preserve prompts, refs, timing and cache identity |
| Smart shot splitting | A | present | Existing detection route plus source timeline integration and boundary selection |
| Run selected shots / output all or selected | A | present | Per-shot selection, real cache/source passthrough for unselected ranges, no invented grey/generated fills |
| Full batch / clip-by-clip | T | present | Stop after one new shot; full batch includes all required outputs |
| Shared references + per-shot local refs | A, T | present | Shared refs remain global, local refs append in stable label order with combined limits |
| Shared prompt + per-shot prompt | A | present | Explicit prepend/append policy rather than implicit fallback replacement |
| External groups and prompt bridges | A, T | present | Typed adapters into the same canonical shot planner |
| Per-shot model LoRAs | A | present | Clone model per shot; native safe loader; hash checkpoint contents; GUI add/enable/strength/remove |
| LoRA previews / metadata | A, D | present | Browse locally installed LoRAs with preview and metadata without changing sampling |
| Per-shot model overrides | A | present | Generic/family models exist; extend with explicit per-shot override packs without patch leakage |
| Image/video/audio RefMods and bundles | D | present | Preserve bundle member identity, strength and descriptions with correct native label ordering |
| RefMod library browser / workflow descriptions | D | present | Rich selection and descriptions; no latent duplication or hidden invalid loads |
| Reference file upload / drop / clipboard / replace | D, A, T | present | Built-in media ingestion into the Director, independent of external graph loaders |
| Reference trim and crop preview | D, A, T | present | Precise file ranges, retained originals, drag handles, playback range and combined duration validation |
| Embedded-video V/A/V+A switching | D | present | Video/audio presentation and native payload agree; pair soundtracks with the correct video |
| Audio extraction from uploaded videos | A, D | present | Safe input storage with content-aware duplicate handling and accurate trim |
| Audio waveforms / playback | D, A, T | present | Show actual decoded waveform and crop bounds, not a decorative waveform |
| Reference image edits / pick source frame as reference | T | present | Non-destructive image adjustments; extract chosen source frame into stable ref identity |
| Role/subject/style/pose/custom reference labels | D | present | Maintain structured roles and mapping across prompt drafts, imports and continuity |
| Structured/free prompt and mention editor | D, A | present | Preserve user text and official labels; aliases resolve without reordering references |
| Prompt Forge / enhancer | D, A | present | DaSiWa-style review/apply workflow; local model, Ollama, or compatible server; optional vision; never auto-apply drafts |
| Multi-shot prompt drafts / context retention | D, A | present | Shot count/descriptions and inherited definitions, with draft invalidation when source context changes |
| Auto aspect / MP / manual resolution | D, T | present | Unified resolution planner; matching UI presets and runtime canvas constraints |
| Input scaling / divisible crop | D | present | Existing resize modes plus divisible crop; apply consistently to all media and endpoint encodes |
| Playback FPS control | D, A | present | Separate native generation time from playback/export rate; keep audio timing explicit |
| Native guides at interior frames | D, T | present | Expose multiple timestamped image/video/audio anchors through native AddGuide |
| Motion continuity in every video mode | A, T | present | Phase-aware AV context pinning; exact added duration; matching prefix trim; not merely last-frame refs |
| Latent checkpoint capture / explicit advance | D | present | Capture completed take, continue from selected checkpoint, stage and explicitly advance source |
| Import/continue an existing video (locked Clip 0) | T, D | present | Original/Auto/Manual working size, source included in full preview/export, source never overwritten |
| Continuity redraw / latent carry | A, D | present | Separate native guide and latent continuation strategies with masks and audio phase handled explicitly |
| Low-resolution carry between SelfLift shots | A | present | Carry valid low-res context and preserve spatially resized conditioning, not just a legacy config flag |
| SelfLift lift/rho/pixel anchor/transition controls | A | present | AIMixer's Euler-state approach and conditioning resize; compare quality and numerical stability |
| Refine with custom model / SIGMAS / passes | A, T | present | Per-pass schedule and configurable sampler; upscale once, then repeated refinement |
| Learned H3 latent upscaler | D, A, T | present | Explicit checkpoint choice, validated architecture, normalized latent handling and original audio preservation |
| Pixel / RTX VSR upscale | A, D | present | Optional provider with clear dependency status; retain pixel and latent approaches |
| Per-step spatial tiled diffusion | D, A | present | Replace independent whole-tile jobs with tile predictions inside a shared sampler trajectory |
| Temporal chunking / memory-aware tile planner | D | present | Plan aligned spatial tiles and overlapping temporal windows under memory budget |
| Upscale endpoint re-encoding / continuation repin | D, A | present | Encode anchors at target canvas and preserve phase-aligned pinned context |
| Face refine tracking / injection / stitch controls | A | present | AIMixer's track/inject/stitch pipeline; supported detectors, correct AV and mask handling |
| Semantic Bridge / adapter switching | A | present | Compatible exact checkpoint, bounded cache, opt-in conditioning rewrite |
| Optional model-scoped residual Cache | D | present | Native block-loop hook when available, no global class modification; version-gated fallback |
| Validation / downstream invalidation | T, A | present | Dependency fingerprints and explicit approval; independent edits do not invalidate unrelated shots |
| Interrupt/save/resume across restarts | T | present | Stable model/checkpoint/LoRA/VAE provenance; per-shot commits and recoverable project state |
| Lightweight project metadata/cache reconnect | T | present | No bulky latents in normal project export, verified fingerprints only |
| Portable packs containing reference assets | D, A, T | present | Optional media-bearing import/export alongside lightweight project mode; validate archive paths |
| Append/overwrite import and missing-file checks | D, T | present | Explicit import policy with label and role remapping, missing assets reported |
| Autosave completed batch / reset project | T | present | Preserve actual seeds and settings; reset only current project state and cache |
| Native VIDEO output / streaming disk assembly | T | present | Real ComfyUI video object; large sequences avoid holding every decoded frame in memory |
| Per-shot export / source passthrough export | A, T | present | Reuse decoded/stored segments, respect selection and seam timing |
| Pre-refine and original-source outputs | A | present | Separate inspectable streams without silently replacing the generated output |
| Per-shot color/exposure adjustments | T | present | Non-destructive decoded grading; keep raw latents/checkpoints unchanged |
| Audio generate/keep source/mute | A | present | Per-shot audio policy synchronized to visible video duration |
| Seam audio correction / channel normalization | A, T | present | Preserve assembled duration; configurable fades and gain matching |
| Video combine / codecs / metadata / preview | D, A, T | present | Existing exporter plus remaining codec controls, real previews and large-output streaming |
| Branding/watermark and seamless loops | D | present | Optional video-output processing with explicit audio/loop timing |
| Progress, previews and detailed execution report | A, T | present | Native callbacks plus per-shot phase/progress and accurate run report |
| Multilingual UI / migrations | A, T | present | One schema with versioned migrations and language-neutral project data |

D = DaSiWa, A = AIMixer, T = Tritant.

## Corrections to the earlier review

1. The earlier blanket rejection of Image Inpaint was based on the generic
   meaning of inpainting, not DaSiWa's actual implementation. The native
   one-image/five-frame feature is restored. Mask-based Fun ControlNet editing is
   a separate optional capability, not a prerequisite for matching DaSiWa.
2. AIMixer's V2V/RV2V uses native reference conditioning plus a source timeline.
   Parity does not require inventing a source-latent denoise-strength workflow.
   Source binding/selection/audio/export are implemented together in this revision.
3. A basic prefix resize is not full AIMixer SelfLift parity. Independent tiled
   samples are not DaSiWa/AIMixer per-step tiled diffusion parity. The Master now uses selected Euler-state and shared-trajectory implementations;
   the older approximations have been removed.
4. Portable media packs and lightweight cache-backed projects are complementary
   features. Keeping only lightweight JSON fails the union requirement.

## Implementation discipline

- Each feature must have backend behavior, usable authoring controls/sockets,
  persistence/migration and error handling as applicable; a config key or node
  name alone does not count as implementation.
- Pin source revisions for comparisons. Do not load three plugins wholesale or
  expose three unrelated directors as a substitute for consolidation.
- Preserve the previous bug fixes while replacing weaker algorithms.
- Source licenses/third-party notices differ. DaSiWa declares GPL-3.0; Tritant's
  third-party notice identifies GPL-derived motion patches despite its Apache
  top-level license. Direct code reuse requires provenance/license handling;
  selected implementations and local native-API adapters are distinguished in
  THIRD_PARTY_NOTICE.md. The combined distribution is GPL-3.0.
- Real GPU validation is necessary to select among competing quality/performance
  techniques. The remote access limitation is a validation blocker, not a reason
  to remove required features from this inventory.

## Local implementation map (1.0.3)

| Area | Entry points |
| --- | --- |
| Director/selection/continuity | `nodes/node_director.py`, `core/source_media.py`, `core/advanced_sampling.py` |
| Authoring/references/LoRAs | `web/js/minimax_director.js`, `core/references.py`, `core/loras.py`, `core/refmod.py` |
| Project/checkpoint/resume | `core/project.py`, `core/cache_manager.py`, `core/provenance.py`, `nodes/node_project.py`, `nodes/node_loaders.py` |
| Sampling/upscale/face | `core/refine.py`, `core/learned_network.py`, `core/tracked_face.py`, selected `core/vendor/` modules |
| Prompt Forge/languages | `core/forge.py`, `core/local_llm.py`, `nodes/node_forge.py`, `web/js/minimax_locale.js` |
| Output/codecs/RTX | `nodes/node_project_video.py`, `nodes/node_video_combine.py`, `nodes/node_video_output.py`, `nodes/node_pixel_upscale.py`, `core/output_processing.py` |

The installed remote ComfyUI and GPU/model-provider checks are deferred at the
user's request. See REVIEW.md for exactly what passed locally.
