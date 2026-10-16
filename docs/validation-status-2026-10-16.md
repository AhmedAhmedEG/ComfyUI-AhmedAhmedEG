# Validation status — 16 October 2026

Validation is still in progress. Earlier completion wording overstated the evidence. Passing unit checks, registering nodes and inspecting their controls do not establish production model inference or output parity.

## Repeated checks

- 221 backend tests passed on the starting 1.7.2 code.
- All six JavaScript suites passed after the new conditional-control fixes.
- 38 CPU tensor/media/provider checks passed before the RTX-helper regression was added. Six parity numerical checks, including the new real import/letterbox/crop regression, then passed.
- Live queue was checked before the three isolated provider jobs. No user jobs were interrupted.

## Live node presentation inventory

All 27 registered nodes were opened in isolated library workflows under `Validation 172`. This checks default presentation and visible contracts; individual mode transitions and model execution require their own evidence. No user graph was overwritten. Initial audit fixture spacing was too narrow for custom panels; wider fixtures were used to inspect those nodes individually. Fixture overlap is not reported as a product defect.

| Group | Nodes inspected | Findings / limits |
|---|---|---|
| Start here | Master, Director Settings | Master editor and normal generation-mode widget present. Settings exposed Auto controls in Manual mode; fixed in 1.7.3. |
| Enhancements | SelfLift, Refine, FaceRefine, Semantic Bridge, Cache | SelfLift exposed inactive split/tile controls; fixed. Refine mode transitions have prior live evidence. Semantic Bridge has no installed adapter. Face model inference remains unverified. |
| Output | Frame Interpolation, Smart Preview, Video Combine, Cached Project/Shot Export, Playback/Watermark/Loop, Pixel/RTX Upscale | Distinct responsibilities and expected sockets. Preview and exporter panels render. Linear interpolation completed live. RTX results below. |
| References and prompts | Reference Pack, RefMod Library, Prompt Forge, Local Prompt/Vision Model | Reference editor and roles inspected with actual connected references in prior live checks, and empty pool now. RefMod library reports zero installed RefMods; local prompt loader reports no LLM. Transformers exposed an irrelevant GGUF projection field; fixed. |
| Checkpoints | Load Take Checkpoint, Advance Staged Take | Compact, distinct load/advance controls and output sockets. |
| Timeline authoring | Project Import, Timeline Builder, Image-to-Video Group, Reference-to-Video Group, Groups Combine | All opened individually. Applying before conversion produces `Convert and review a project first.` Typed importer-to-Master integration passed in the earlier live job. |
| Advanced graph tools | Tail From Latent, Clip Model Pack, Review/Apply Prompt Draft | Compact natural layouts checked individually. Review/Apply exposes STRING output 0 and typed timeline output 1. Tail retains the documented `video_vae` compatibility alias alongside `vae`; this is not a second node. |

Additional presentation debt: generic authoring panels reserve a large empty area when no RefMods/references/clips are available. It is visible and should not be described as polished merely because the controls render.

## New actual execution results

| Job | Actual result |
|---|---|
| `21fdd335-9620-4c75-bb0e-81a5cb28c14f` RTX pixel | Failed during import: missing `Tuple`. Inspection also found missing `torch.nn.functional as F` in the letterbox path. Both imports fixed in 1.7.3; requires deployed rerun. |
| `cf15b4ec-0951-4335-a8d9-60b5aca8db23` RTX interpolation | Actionable dependency error: installed `nvidia-vfx` lacks `VideoFrameGeneration`. No successful RTX interpolation is claimed. |
| `945cee63-e6b2-4b97-b273-d26e08bd811e` Linear interpolation | Completed successfully: two input frames yielded four saved output frames. |

Local full job history: `.validation/optional-providers172-results.json`. Small synthetic image fixtures validate execution contracts, not perceptual interpolation quality.

## GPU failure evidence supplied by the user

The supplied September 14 log records explicit interruptions during initialization, successful eight-step runs, and then a fatal `c10::AcceleratorError`: `CUDA_ERROR_INVALID_VALUE` from `cuMemFreeAsync`. The Python stack runs through the SLA attention plugin into `comfy_kitchen.backends.eager.sol_attn`. It proves that particular process aborted in the CUDA allocator/attention path, not that the Master raised an ordinary Python error. It does not establish the ultimate cause, nor can its different timestamps/prompt IDs be equated with the October validation jobs.

The currently running server reports PyTorch 2.14.0+cu130, comfy-kitchen 0.2.33, comfy-aimdo 0.5.3, `--use-sage-attention`, and cudaMallocAsync. No host allocator/attention launch flags have been changed during this audit.

## Remaining required evidence

- Native-versus-Master successful diffusion comparison, every generation mode and continuity path with actual models, per-clip LoRA effect/isolation and production dimensions.
- Actual SelfLift, learned latent upscale, tiled/refine passes, face model and Semantic Bridge inference; SDK-capable RTX execution.
- Matched runtime, peak VRAM/RAM measurements and real vision proposal/appearance accuracy.
- Updated conditional controls visually checked on a fresh deployed frontend; RTX pixel rerun after the import fix.

These remain open, not passed by inference. Missing model/SDK dependencies and the unresolved native initialization outage are concrete limits on end-to-end certification.
