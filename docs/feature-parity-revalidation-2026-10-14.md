# Consolidation parity revalidation — 14 October 2026

## Verdict

Audited our commit `bd975262b085164a914998d41d7eaa55371b2abc` (package 1.5.1).
The main MiniMax generation, continuity, reference, enhancement, project and output
paths are implemented. **Complete feature parity is not established.** Several
source controls and operational behaviors remain different or incomplete. No
comparative GPU measurements establish that every overlapping implementation is
the best for output quality, latency or peak memory.

This is a read-only implementation audit with local checks and a new report.
No generation was queued, no server connection/proxy was started, no server was
updated/restarted, and no implementation changes were made.

## Scope and source evidence

Compared source code, public schemas, current editor controls and runtime consumers,
using the retained original consolidation snapshots in `.validation/upstream-parity/`:

| Project | Original baseline |
|---|---|
| [DaSiWa](https://github.com/darksidewalker/ComfyUI-DaSiWa-Nodes/tree/aedf3592e57650494f68b4c8fb7f45edc25ca933) | `aedf3592e57650494f68b4c8fb7f45edc25ca933` |
| [AIMixer](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director/tree/a8f57b8e23c46ee28fdb96796510fa7b4f3b1fbb) | `a8f57b8e23c46ee28fdb96796510fa7b4f3b1fbb` |
| [Tritant](https://github.com/tritant/ComfyUI_MiniMax_H3_Extender/tree/1cf9bb966c2692359ac843c196454ba436ee1201) | `1cf9bb966c2692359ac843c196454ba436ee1201` |

This report does not claim to cover new upstream commits since the October 12
review. It concerns the original three-project consolidation. Unrelated DaSiWa
utilities are outside the MiniMax/video feature union.

Evidence levels are kept separate: a runtime path, an accessible authoring control,
a passing local contract, and a real H3 GPU result are different things. “Covered”
below means source-level and local-contract coverage, not matching images or speed.

## Coverage and ownership

| Capability | Current owner and evidence | Assessment |
|---|---|---|
| Text, initial image, first/last and closing-only modes; REF2V; source V2V/RV2V; single-image five-frame pass | Master; `core/task_modes.py`, `core/executor.py`, `nodes/node_director.py`; runtime contract tests | Core routes covered. Source task names and defaults differ. Single-image Inpaint is not a mask editor in either implementation. |
| Per-clip prompt, duration, uint64 seed; common prompt; fixed clip type | Master editor, `core/project.py`; editor and runtime tests | Covered. Fixed types and English-only UI are intentional user requirements. |
| Reference selection, ordered native labels, audiovisual pairing, media limits | Reference Pack + Master; `core/references.py`, `core/asset_editor.py`, `core/source_media.py`; real pack-source tests | Covered. New Clip uses connected assets; file ingestion lives in Reference Pack. Pool availability does not mean every reference is sent to the model. |
| Trim, crop, exposure/contrast/saturation, scaling, video/audio/frame presentation, uploads and frame picking | Reference Pack editor in `web/js/minimax_authoring_tools.js`; `core/asset_editor.py` | Main editing functions covered. Arbitrary procedural graph transforms cannot be reconstructed from loader filename previews. |
| RefMod selection, descriptions and strength; bundles/native conditioning | RefMod Library -> Reference Pack -> Master; `nodes/node_refmod_library.py`, `core/refmod.py` | Dedicated owner restored. Installed compatible assets remain required. |
| Source range split/equal split/merge, scene detection | Master and source helpers; editor tests | Covered. File-based scene detection needs a real source file. |
| External image/reference groups | Group nodes -> Timeline Builder -> Master `timeline`; `core/timeline_input.py` | Earlier orphan-node gap closed. Builder owns authoring when connected; Master does not compete with it. |
| Next Clip and All Clips; approved saved-take reuse | Master skip path, lazy model routing, cache restore; runtime tests | Covered. Approved missing takes raise an error rather than silently regenerate. Approval is deliberately different from upstream run-selection flags. |
| Motion Context, Latent Carry, endpoint handoff and independent clips | `core/continuity.py`, `core/advanced_sampling.py`, Master | Main paths covered; real CPU checks exercise tail copy, AV masks and prefix trim. Previous timeline clip is the authoring source. GPU motion quality is unverified. |
| Interior image/video/audio guides and latent checkpoints | Master guide editor; checkpoint/advance nodes; runtime helpers | Paths available. Guide model behavior and real checkpoint continuation quality need H3 runs. |
| Per-clip LoRAs and named model overrides | Master, `core/loras.py`, model pack | Covered locally, including resumed refinement, approval invalidation and unmatched-adapter error. Raw LoRA state cache is bounded to eight entries per execution; complete patched stacks are rebuilt and are not persistently cached. |
| SelfLift progressive sampling and low-resolution carry | SelfLift pack + selected AIMixer Euler-state implementation | Main algorithm retained. No comparative quality or VRAM benchmark. |
| Learned latent upscale, tiled refinement, temporal chunking, custom model/SIGMAS | Refine pack; `core/refine.py`, selected DaSiWa shared-trajectory implementation | Main algorithm paths retained. Refine control parity remains partial; see findings. |
| First-pass review and numbered intermediate outputs | Refine + Master stage cache + Smart Preview/Project Video | Earlier gaps closed; stage fingerprint and local preview/export checks pass. |
| Face detection/tracking/injection/stitching; Semantic Bridge; residual model cache | Dedicated enhancement packs and runtime helpers | Paths exist, source algorithms retained/adapted. Actual detector, bridge weights and GPU interactions are unverified. |
| Prompt drafting, providers, review/apply, history, creativity/detail, optional vision | Forge node/editor, `core/forge.py`, `core/local_llm.py` | Earlier practical review integration restored. Rich DaSiWa cast/continuity/provider behavior remains partial. |
| Named server projects, workflow reconnect, autosave, portable media, take cache and restart recovery | Project/cache/provenance helpers and routes; regression tests | Core storage covered. Foreign project/caches are only partially convertible. |
| Full/latest/staged preview, mixed-resolution export, clip-ID export, originals/audio | Smart Preview and Project Video; actual CPU encoding tests | Earlier exporter gaps closed. Explicit clip IDs replace ambiguous retired “selected” UI. |
| Codecs, watermark, loop, playback rate and RTX/linear interpolation | Dedicated output nodes and selected encoder/RTX modules | Implemented paths available. Linear interpolation is blending, not optical-flow motion estimation. Optional RTX GPU execution is unverified. |
| Output grading and seam audio fades/gain matching | Per-clip grading + shared output-audio settings | Core paths covered. Output joins are distinct from continuity conditioning/seam refinement. |

## Confirmed remaining differences and gaps

### 1. Refine seed policy is missing

AIMixer's pinned `nodes/director_refine.py` and `director/refine_pack.py` expose
`inherit`, `offset`, and `independent`, including a separate refine seed. Its
`refine_seed_for()` keeps the inherited seed for each pass, adds an offset when
requested, or uses the independent seed without altering the first-pass seed.

Our `nodes/node_refine.py` has no refine seed controls. `core/refine.py` supplies
`seed + index` / `seed + pass_index`. A per-clip first-pass seed is not a replacement
for an independently rerollable refine seed. This is a real baseline parity gap
and a reason equal visible first-pass settings need not produce equal refined output.

**Owner:** Refine node. Add an explicit validated seed policy/uint64 seed, preserve
first-pass cache identity when only refinement changes, and test every pass seed.

### 2. Refinement canvas and pass range are narrower

AIMixer follows the first-pass aspect with a megapixel target and allows up to
9999 refinement rounds. Its legacy aspect control is already deprecated upstream;
that deprecated widget should not be copied. Our Refine accepts only explicit
target width/height (32-pixel steps, maximum 4096 each) and caps rounds at 20 in
both schema and runtime. Entering a different aspect is possible.

Explicit dimensions provide useful control but do not replace automatic
aspect-preserving MP sizing. The cap is a deliberate bounded implementation,
not evidence of complete configurable parity.

**Owner:** Refine node. Add Follow First Pass + MP and Manual sizing; resolve at
runtime from the actual latent, persist the policy, and expose any intentional
round/canvas limit clearly. Raising limits alone is not a quality improvement.

### 3. Pixel resize controls are inconsistent, and Lanczos is absent

`nodes/node_pixel_upscale.py` exposes Center Crop (Fill) and Letterbox (Fit), but
the bicubic/learned-pixel branch directly calls `F.interpolate(...size=(height,width))`.
Only the RTX branch uses `_fit_frame_to_target_aspect`. The CPU branch stretches
the image and ignores the selected policy. A real-tensor reproduction produced
identical results for Fill and Fit on a 2:1 image resized to a square.

AIMixer also offers Lanczos pixel preparation before refinement. Our integrated
choices are latent, learned pixel, RTX VSR and bicubic. Bicubic availability does
not establish that it is the strongest replacement for Lanczos.

**Owners:** Pixel Upscale and Refine. Apply a common aspect policy to all providers,
add Lanczos where it is appropriate, and propagate policy through refine. Test
crop/padding pixels and endpoint re-encoding, not just output shape.

### 4. Forge does not reproduce DaSiWa's complete cast/retention authoring

The current UI restores reviewed apply, three drafts, creativity/detail, source
metadata, optional file-backed pictures, and shot-description JSON. It does not
implement DaSiWa's numbered character grouping, several-character combinations,
left/right positions, per-reference Keep/Ignore controls, verified media mapping,
or equivalent structured subject/retention compilation. Our generic role list
and free description are useful but weaker for those operations.

DaSiWa supplies chronological continuation source-tail frames to appropriate
vision drafts and detailed mode-specific rules. Our browser request chooses pool
assets with filenames; `core/forge.py` supplies a generic instruction and the
existing timeline. This is not equivalent source-tail/cast handling. Shot
descriptions are a JSON widget rather than individual per-shot text boxes.

**Owners:** Reference Pack for cast/retention metadata; Forge for prompt-specific
editing, stable label compilation, chronological tail context, and draft review.
Keep file ingestion out of the Master clip popup.

### 5. Forge model residency and cancellation are weaker operationally

DaSiWa's manual describes unloading local models after use and refusing a new
Forge generation while sampling. Our `core/local_llm.py` keeps one callable in a
module cache; the closure retains its model, potentially on CUDA. It has no
explicit after-draft unload/offload lifecycle. A graph-held callable may also
retain a previous provider even after the cache dictionary is cleared.

Cancel aborts the browser request and rejects late responses. It does not prove
the provider computation stops. The remote Forge HTTP call is blocking with a
timeout; there is no equivalent guaranteed provider cancellation or sampling
queue guard in the inspected draft path.

**Owner:** Forge provider lifecycle/routes. Add explicit release/offload policies,
a sampling guard and cancellable jobs where the provider supports them. Measure
VRAM rather than describing dictionary clearing as GPU memory release.

### 6. Project Import is metadata conversion, not faithful project restoration

`core/project_conversion.py` recognizes several foreign envelopes, extracts media,
preserves selected prompt/seed/source fields and resets foreign approval. It does
not import compatible foreign latent caches or sampler/model bindings. Foreign
LoRAs, guides and RefMods are omitted with warnings. Continuity is set to
Independent with 22-frame contexts rather than preserving the source choices.
This was reproduced using an AIMixer clip with Latent Carry and guides/LoRAs.

Even the `current` conversion path reconstructs a subset of clip fields; use the
normal project loader for faithful current-project reopening. Some fields such
as continuity and source/RefMod semantics need explicit mappings, not a successful
ZIP extraction claim. Tritant's automatic upscaler weight download is also not
replicated; models must be installed separately.

**Owner:** Project Import. Publish a supported-field matrix and map authoring
settings without claiming sampler/latent equivalence. Model and foreign-cache
conversion need explicit compatible formats and provenance checks.

### 7. End-to-end memory/quality superiority remains unproven

Project Video uses clip-at-a-time disk-backed export. Master still accumulates
decoded outputs for its direct IMAGE/AV result. That is not the same memory
behavior as Tritant's streaming assembly for long full batches. The new safe
H3 offload and version-gated boundary cleanup paths exist, but are not measured
proof of lower VRAM or immunity to OOM.

**Owners:** Master output/cache boundary and Project Video; optional enhancement
backends. Offer an explicit cache-only/disk-backed output path for large runs,
then compare peak RAM, peak VRAM, time and output quality with the same models,
native versions, seeds, references, sigmas and frame counts.

## Which overlapping approaches were retained?

| Subsystem | Retained choice | Why / evidence boundary |
|---|---|---|
| Ordinary conditioning/sampling | Direct native H3 nodes and scoped wrappers | Native compatibility and explicit AV routing; avoids importing three plugin registries or unused global context patches. Actual seeded equality depends on the whole pipeline. |
| Motion and progressive lift | AIMixer phase-aware continuation and Euler-state SelfLift | Preserves masks/audio phase and low-resolution carry instead of substituting a last-frame-only reference or simple prefix resize. Numerically exercised; not GPU-benchmarked. |
| Global tiled refine | Selected DaSiWa shared-trajectory sampler/planner | Per-step tile predictions share a trajectory; stronger algorithmic match than independent finished-tile jobs. Modern upstream changes are not automatically included. |
| Face refine | AIMixer/Carasibana tracking, native injection and stitch helpers | Retains the multi-stage algorithm. Detector and quality require actual weights/GPU validation. |
| Long projects | Tritant-style per-clip durability, adapted server project identity and approval | Saves real artifacts and restores approved takes without accidental regeneration; server persistence adds multi-session use. Streaming parity does not extend to every Master output. |
| Asset authoring | Dedicated RefPack editor with native stable IDs | One configuration owner, richer crop/trim/media editing, compatible with the user's pack-only clip selection. This is an integration choice, not identical upstream UX. |
| Forge | Reviewed separate node with local/remote providers | Preserves explicit review and avoids graph cycles. Current generic cast/provider handling is weaker than the full DaSiWa approach. |
| Export | Cache-aware mixed-canvas Project Video plus adapted DaSiWa encoders | Actual encoding checks verify streams and enclosing canvas. CPU pixel resizing still needs the correction above. |

“Best approach” is a subsystem-specific engineering judgment until controlled
GPU comparisons exist. Do not replace this distinction with a single blanket
“best of all three” claim.

## Earlier audit gaps that are now closed locally

The October 12 review is historical, not the current status. The following have
usable paths and tests after 1.5.1:

- Export chosen clip IDs, cached pack footage without a live filename, and mixed
  resolutions at an enclosing aspect-preserving export canvas.
- Group nodes integrated through Timeline Builder's typed Master input.
- Dedicated asset editor and RefMod descriptions/strength, with one asset shown.
- First-pass approval, default FL2V refine skip, pixel preparation before refine,
  and per-refinement-round cached preview/export streams.
- Forge's Master chooser, reviewed apply/history, creativity/detail and cancel UI.
- Explicit Project Import and interpolation nodes, experimental Spike Guard,
  and safe runtime memory-lifecycle hooks.
- Subsequent clip LoRA fixes, event-sequence progress recovery, chain continuity
  markers, and removal of the chain badge background.

These fixes narrow the original gaps; they do not erase the partial behaviors
listed above. `FEATURE_PARITY.md`'s historical all-present inventory should be
read as a broad implementation map, not as proof that every source control survived.

## Verification performed

- 178 backend regression tests passed: `python -m unittest discover -s tests`.
- 13 additional real tensor/media tests passed across
  `validation.test_parity_numerical`, `validation.test_continuity_numerical`, and
  `validation.test_pack_source_numerical`; includes actual CPU encoding/decoding.
- Editor, authoring-tools and preview-node JavaScript suites passed.
- Two direct CPU reproductions confirmed ignored CPU Fit/Fill policy and lossy
  foreign continuity/guide/LoRA conversion. Script retained locally as
  `.validation/parity_recheck_20261014.py`.

Model calls in contract tests are controlled fixtures. No H3 generation,
optional model-weight execution, RTX SDK run, peak-memory measurement or visual
quality comparison was performed in this audit. These tests are meaningful
coverage of selected paths, not exhaustive proof for every UI/control combination.

## Recommended implementation order

1. Correct Pixel Upscale's ignored aspect policy; expose any stronger resize
   alternatives without silently changing existing workflows.
2. Complete Refine seed policies and aspect/MP sizing with stage-cache tests.
3. Complete Forge cast/retention compilation and local model lifecycle.
4. Make foreign project conversion field-preserving where compatible and explicit
   about every omitted field; keep normal current-project load lossless.
5. Add/validate Master disk-backed large-run output, then run controlled GPU
   comparisons before making quality/performance superiority claims.

These are proposed next steps. This audit did not implement or deploy them.

## Implementation follow-up

The findings above describe the audited 1.5.1 baseline, not the current working implementation. See [1.6 implementation and validation](parity-implementation-1.6.md) for resolved gaps, current upstream reconciliation and remaining external boundaries.
