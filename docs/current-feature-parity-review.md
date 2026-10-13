# Current consolidation parity review

**Historical baseline:** the findings below describe 1.4.22 before the follow-up implementation. See [the complete 1.5 audit additions](release-1.5-audit-additions.md) for what 1.5.0/1.5.1 added and the remaining verification limits.

Reviewed 12 October 2026. Target: release **1.4.22**, commit `683fabf378decfa8e7aa67338d774ec3f26c13a8`.

**Conclusion: the core generation union is implemented, but complete usable feature parity is not established.** The older inventory's blanket “present” statuses are no longer accurate after the interface changes. Backend code, a registered node, and a usable current workflow are different levels of support.

This review inspected original pinned snapshots and current upstream snapshots downloaded directly from GitHub. None of the upstream plugins were installed or executed. The current server was not modified or restarted. Small real CPU reproductions were used for the exporter findings; H3 GPU quality/performance comparisons were not run.

## Comparison revisions

| Project | Original consolidation baseline | Current upstream checked |
|---|---|---|
| [DaSiWa](https://github.com/darksidewalker/ComfyUI-DaSiWa-Nodes) | `aedf3592e57650494f68b4c8fb7f45edc25ca933` | `bdb62d4c561bbed30351974844e0168ad471331a` |
| [AIMixer](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director) | `a8f57b8e23c46ee28fdb96796510fa7b4f3b1fbb` | `8151b291fcacee5ddb70c6493eaed4f831bc6867` |
| [Tritant](https://github.com/tritant/ComfyUI_MiniMax_H3_Extender) | `1cf9bb966c2692359ac843c196454ba436ee1201` | `60efaf15c589d6671ef43e7c0946913a54221865` |

“Preserved” below means there is an accessible current implementation, with local contract evidence where available. It does not mean bit-identical seeded output, identical defaults, or benchmarked quality parity. “Changed intentionally” denotes the current product design, including explicit user requests. “Partial/missing” denotes an unresolved capability or integration gap.

## Preserved generation and supporting capabilities

| Capability | Source lineage | Current implementation and difference |
|---|---|---|
| T2V, I2V, first/last frames, closing-only frames | All three | Native H3 endpoints through one Master; separate fixed clip types rather than one mutable global task. |
| REF2V multimodal conditioning | All three | Connected pack IDs, ordered native labels and paired video soundtracks. Pool can grow through chained packs; each clip has native asset limits. |
| V2V / RV2V source edits | AIMixer | Source range bound to Video 1, optional extra references for RV2V; native reference-conditioned generation. |
| Single-image Image Inpaint | DaSiWa | Five-frame native pass exposing a final still. Neither this nor the source feature is a mask editor. |
| Per-clip prompt, duration and uint64 seeds | AIMixer/Tritant | Editor persistence and seed advancement tested; durations obey the native frame grid. |
| Shared prompt and structured/free prompts | DaSiWa/AIMixer | Shared prompt under timeline, prepend/append; structured backend and reference-token insertion remain. |
| Clip LoRAs, model overrides | AIMixer/Tritant | Per-clip adapters, strength/enable controls and named model pack. LoRA metadata/preview lookup remains. |
| Source split/equal split/merge and smart split | AIMixer | Range editing preserved; scene detection is optional and file-backed, so a pure procedural IMAGE batch cannot use file-based scene detection. |
| Independent / Motion Context / Latent Carry / endpoint handoff | All three | Explicit per-clip choices with separate video/audio context, prefix trimming and visual overlays. Algorithms are consolidated, not copies of each source's complete execution engine. |
| Interior image/video/audio anchors | DaSiWa/Tritant | Native AddGuide placement in seconds; offsets account for continuity prefix. |
| SelfLift | AIMixer | Euler-state, lift/rho/anchor/transition and low-resolution carry implementation retained. Actual weights/GPU output quality unverified. |
| Learned latent upscale, refinement, custom model/sigmas/passes | All three | Available through Refine; shared-trajectory spatial/temporal strategy selected from DaSiWa. Not every upstream refine control/workflow is present; see below. |
| Tracked face refinement and Semantic Bridge | AIMixer | Dedicated connected packs; missing/broken connected bridge fails visibly. Actual detector and adapter inference not validated here. |
| Model-scoped residual cache | DaSiWa | Optional separate cache patch node. Runtime/version-specific behavior still needs live model benchmarks. |
| Source/generated/mute audio; join fades/gain matching | AIMixer/Tritant | Clip Audio and timeline output finishing have distinct owners. |
| Grading, watermark, simple seamless loop, playback rate | DaSiWa/Tritant | Decoded/output processing paths remain. The simple loop is not equivalent to newer optical-flow/RTX interpolation. |
| Native VIDEO, codec export, pre-refine/source streams | All three | Output through dedicated nodes; streams moved from the Master's direct sockets to Project Video. Exporter parity has specific bugs below. |
| Atomic takes, autosave, saved checkpoints, resume | DaSiWa/Tritant | Stable project/clip identity, disk artifacts and checkpoint/advance graph tools. Workflow/project formats differ from upstream. |

## Deliberate product differences

| Difference | Current behavior | Consequence |
|---|---|---|
| Media ingestion | New Clip selects injected RefPack assets; no upload inside the popup or separate top-bar Add Video. | Deliberate single configuration owner. Upstream in-node upload/drop/clipboard is not an additional feature to restore in the Master. Rich asset editing still needs a separate owner. |
| Clip types | Type fixed after creation; colored code beside name. | Prevents stale incompatible references after switching type. |
| Continuity source | Previous timeline clip only; imported footage must occupy the timeline. | Removes off-timeline video continuation choices. Advanced latent checkpoint socket remains separately available. |
| Approval versus run selection | Card checkbox approves a real saved take; green means reuse. Next Clip/All Clips choose generation scope. | The old upstream “run checked clips” UI was intentionally removed. Legacy selection API compatibility is not a current authoring control. |
| Accepted output | Approved takes survive global settings changes and bypass conditioning rebuilds. | To replace a saved take, unapprove it. This differs from stricter dependency-driven invalidation policies. |
| Preview | Separate Smart Preview, latest by default; Full Video explicitly reads available cached takes. | Preview is not embedded as an additional Master configuration surface. |
| Configuration ownership | Sampling/canvas in Settings, assets in RefPack, prompt drafting in Forge, per-clip authoring in Master. | Dedicated nodes instead of repeating their settings inside the Master. Usable integration must still exist. |
| Language | Current editor English only. | Intentional removal of language switching; older README/i18n claims are stale. |
| Storage | Named projects/workflows and large take artifacts live on the server. | Adds multi-session reopening; no requirement to download bulky latents. Lightweight/portable formats are project-specific. |
| Models | Separate lazy FL2VA/REF2VA inputs with stock loaders. | Changes source wiring; old external workflows are not drop-in compatible. Next Clip loads only the needed unapproved clip family. |

## Confirmed gaps and partial parity

### 1. Advanced Project Video export is out of sync with the new timeline

Three failures were reproduced against the actual export method with real CPU tensors, isolated filesystem caches, and a controlled encoder (no GPU/server changes):

* **Selected export:** it still checks `selected`, while the current editor writes `validated` and clears the retired selection flag. A normal approved clip therefore produces “There are no shots to export for this selection” with selection=selected.
* **Existing pack video:** a locked clip with `source.ref_id` calls source_range without the injected pack and does not fall back to its cached frames. Even with a complete cached take, export reports “The selected source video is not in the connected Reference Pack.”
* **Mixed resolution:** unlike the fixed Master and Smart Preview, this exporter uses the first clip's canvas. A 32×64 clip followed by a 96×32 clip was encoded twice as 32×64; later resolution is reduced. Its fit/pad operation preserves aspect, but the resolution policy differs.

Evidence: `nodes/node_project_video.py`, particularly its selection filter, locked/source branch, and first-canvas assignment; `core/source_media.py`. Reproduction: `.validation/reproduce_parity_gaps.py`.

### 2. External group nodes have lost ordinary graph integration

Image-to-Video Group, Reference-to-Video Group and Groups Combine are registered and emit `MMX_DIR_GROUP`. Master no longer exposes i2v_groups or r2v_groups. Legacy Python/API paths still accept these kwargs, and existing tests exercise those paths, but that does not make the registered group nodes usable in a new normal graph. This is an orphan-node integration gap after socket simplification, not full parity with AIMixer's external-priority batches.

Evidence: `nodes/__init__.py`, `nodes/node_groups.py`, `MiniMaxH3MasterDirector.INPUT_TYPES()` versus execute/check_lazy_status legacy arguments.

### 3. Rich reference editing is not available in the current authoring surface

The current RefPack exposes names and media/RefMod inputs. Master selects those assets and previews them, but does not expose upstream's complete crop/trim/edit workflow, actual waveform drag handles, video V/A/V+A switching, frame picking, or Character/Place/Style/Pose/Custom role editor. Backend loaders, edit helpers and routes remain; they are not equivalent to an accessible UI. Source-video range controls and per-clip output grading are separate preserved capabilities.

DaSiWa's RefMod browser/descriptions/strength controls are also not replicated by the current two string inputs: pack-derived RefMods are assigned default strength 1.0 and descriptions derived from their names. Advanced timeline refmod rows exist, but ordinary pack controls do not expose their full authoring contract.

Evidence: `nodes/node_ref_pack.py`, `web/js/minimax_director.js` asset picker/preview code, `nodes/node_director.py` pack-to-refmod rows, `core/references.py` and `core/refmod.py`.

### 4. Refine preserves the main algorithm but misses AIMixer workflow features

* No confirm_first_pass gate that caches first pass, lets the user inspect it, and runs only refinement on a subsequent queue.
* No skip_fl2v control/default. Our refinement can re-encode endpoints and repin context, but that is different from skipping the pass to protect keyframes.
* No integrated pixel/RTX upscale-method choice feeding the upscale into the refine pass. Learned Pixel and RTX upscalers exist as separate decoded-image tools; standalone processing is not the same pipeline operation.
* No per-refinement-round image/file outputs. We store pre-refine and final output, not every pass.
* Pass count capped at 20 rather than AIMixer's 9999; target controls use explicit width/height rather than its full follow/aspect/MP preset interface.

Evidence: [AIMixer pinned Refine source](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director/blob/a8f57b8e23c46ee28fdb96796510fa7b4f3b1fbb/nodes/director_refine.py), `nodes/node_refine.py`, `core/refine.py`, `nodes/node_pixel_upscale.py`.

### 5. Forge exists, but differs substantially from DaSiWa's reviewed writing workflow

Our separate Forge/Apply nodes can generate and apply timeline JSON, with local Transformers/GGUF, Ollama or compatible providers, optional vision, and context invalidation. The current Master does not offer a first-class draft-review/apply connection surface. Using timeline JSON/advanced hidden input wiring is different from a usable dedicated prompt-pack integration; connecting Master output back to itself through Forge would create a graph cycle.

DaSiWa's creativity/detail controls, three-draft history, role-driven cast editor, mode/continuity-specific writing rules, cancellation UI and per-shot description boxes are not fully reproduced by our simpler instruction/count/provider nodes. Moving Forge out of Master was requested; losing these functions or its practical integration was not a necessary consequence.

Evidence: `nodes/node_forge.py`, `core/forge.py`, current Master schema, [DaSiWa pinned Director/Forge manual](https://github.com/darksidewalker/ComfyUI-DaSiWa-Nodes/blob/aedf3592e57650494f68b4c8fb7f45edc25ca933/docs/minimax_h3_director.md).

### 6. Native upstream workflow/project compatibility is not supplied

Our project/archive schema and node IDs are our own. There is no complete importer for Tritant .ext projects, AIMixer's mmxpack structure, or every DaSiWa reference pack/workflow. Local legacy Master migrations do not migrate those three external formats. Compatibility requires explicit conversion rather than assuming functional consolidation makes saved workflows interchangeable.

Tritant's automatic upscaler download is also not duplicated; compatible weights must be installed explicitly. This is an operational difference, not a missing learned-upscale algorithm.

## Newer upstream work outside the pinned consolidation baseline

These are latest-snapshot differences, not claims that the original baseline was already missing them:

* **DaSiWa:** new experimental learned-latent Spike Guard; newer RTX pair frame generation and related loop options; revised native-sampler/noise integrations and memory-budget planning/enforcement. Our vendored tiled implementation derives from the older pinned source and has local adaptations, so current upstream controls and fixes are not automatically included. Its latest Forge/source-binding and memory-reclamation fixes likewise require selective review; the entire upstream delta was not ported.
* **AIMixer:** subsequent execution/cache/audio fixes and between-segment DynamicVRAM prefetch cleanup. Our implementation does not have the same explicit prefetch cleanup sequence; no equivalent performance guarantee has been measured.
* **Tritant:** 3.0.12 adds targeted VAE/text-model offload before refinement, AIMDO cleanup at Full Batch clip boundaries, and editor cache-identity updates. Our runtime lacks that specific offload/prefetch/cast-buffer/watermark sequence. Our project identity design differs, so its editor-identity fix is not automatically applicable.

Sources: [DaSiWa latest tiled manual](https://github.com/darksidewalker/ComfyUI-DaSiWa-Nodes/blob/bdb62d4c561bbed30351974844e0168ad471331a/docs/minimax_h3_tiled_upscale.md), [RTX frame generation](https://github.com/darksidewalker/ComfyUI-DaSiWa-Nodes/blob/bdb62d4c561bbed30351974844e0168ad471331a/docs/rtx_frame_generation.md), [AIMixer latest cleanup](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director/blob/8151b291fcacee5ddb70c6493eaed4f831bc6867/director/vram_cleanup.py), [Tritant latest execution](https://github.com/tritant/ComfyUI_MiniMax_H3_Extender/blob/60efaf15c589d6671ef43e7c0946913a54221865/extender.py).

## Validation boundary and next priorities

The 160 backend regressions and current editor/media tests validate many retained controls, not complete source-project parity. A legacy-kwargs test can pass even when a public socket is gone. A helper can be correct without a reachable editor. We have no comparative H3 quality, speed, peak VRAM, full-batch RAM or optional-provider benchmark. Master still materializes its direct decoded sequence in RAM; cache-backed preview/export has different memory behavior. “Best of all three” remains an engineering intention, not a benchmark result.

Recommended order: repair Project Video contracts; reconcile orphan group nodes and Forge's external integration; supply rich asset/RefMod controls in their dedicated owner; add missing two-stage refine controls; then selectively review newer upstream memory and quality features with GPU measurements. Keep the intentionally simplified Master UI, fixed clip types, approval policy and pack-only asset selection.
