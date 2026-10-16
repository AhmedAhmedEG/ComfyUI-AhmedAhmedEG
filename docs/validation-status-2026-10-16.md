# Validation status — 16 October 2026

Validation is still in progress. Earlier completion wording overstated the evidence. Passing unit checks, registering nodes and inspecting their controls do not establish production model inference or output parity.

## Repeated checks

- 223 backend tests passed after the preparation/provenance and refinement-status follow-up fixes (221 on the starting code).
- All six JavaScript suites passed after the new conditional-control fixes.
- 40 CPU tensor/media/provider checks passed, including the new real RTX-helper import/letterbox/crop regression.
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

Follow-up layout fix: empty RefMod/reference editors now shrink to their controls, and the export selection panel appears only for explicit clip selection. These transitions have JavaScript regression coverage; live verification of the follow-up deployment is recorded below.

## New actual execution results

| Job | Actual result |
|---|---|
| `21fdd335-9620-4c75-bb0e-81a5cb28c14f` RTX pixel | Failed during import: missing `Tuple`. Inspection also found missing `torch.nn.functional as F` in the letterbox path. Both imports fixed in 1.7.3; successful deployed rerun below. |
| `cf15b4ec-0951-4335-a8d9-60b5aca8db23` RTX interpolation | Actionable dependency error: installed `nvidia-vfx` lacks `VideoFrameGeneration`. No successful RTX interpolation is claimed. |
| `945cee63-e6b2-4b97-b273-d26e08bd811e` Linear interpolation | Completed successfully: two input frames yielded four saved output frames. |
| `1c248619-e569-4a5e-97cc-a8a551422923` RTX pixel, deployed rerun | Completed successfully after the import fix. |
| `4b607166-6a95-476f-9415-d18e6d6766d5` RTX interpolation, rerun | Same explicit missing-SDK-capability error; remains unavailable. |
| `4300c076-759a-4fed-b38b-7aecfa5cd172` native / `43d574af-ce29-4b16-bdb6-09c20abe68a8` Master | Both completed. Same installed FL2VA checkpoint, CPU text encoder, prompt, seed 8675309, Euler/simple, shifts 12/3, CFG 1, one step, 128×128, five frames. Video tensors `[1,24,2,8,8]` and audio tensors `[1,32,2,8]` are exactly equal: maximum absolute difference 0.0 for both. |
| `8ff2aa63-c80f-4dc2-9f46-038f3e32f67c` learned latent upscale | Completed actual installed 3D upscaler inference. Output video latent is `[1,24,2,16,16]`, corresponding to requested 256×256 from a 128×128 first pass. |
| `190ec67f-bb39-4af0-8a9e-b58667f0a29d` SelfLift | Completed three steps. Live log confirms 128×128 → 64×64 low resolution, two low steps + one high step, and learned transition `[1,24,2,4,4]` → `[1,24,2,8,8]`. |
| `d70cb290-207b-4e56-9c6e-7d4d6fc6eae2` global refinement | Completed with two configured refinement passes and independent refine seed 4242. Report confirms global full-canvas path and enforced heuristic planning. |
| `dcfc126e-c7e8-40ab-b98b-0a3620a17a37` tiled refinement | Completed sampler-backend refinement with spatial tiling enabled, two tiles and 16px overlap. |
| `77141b73-5f08-4bd1-80bb-a6946c35babb` keyframe modes | I2VA, L2VA, FL2VA and Image Inpaint all completed from an injected two-image pool. Generated four clips; visible outputs 5+5+5+1 = 16 frames, no cache errors. |
| `d7378edf-f1d0-48b3-ba14-f520f900668d` reference/video modes | REF2VA, V2V and RV2V generated successfully; an existing-video clip passed its original five frames through. Three generated clips + one source clip = 20 assembled frames, no cache errors. Together with T2VA and keyframe cases, all eight generation types have actual tiny-model execution evidence. |
| `57e4c884-615c-4fcf-a265-26e04f1ff89a` per-clip LoRA / `4e2f4e65-4d47-4599-86ad-b7fa41e85c4b` checkpoint readback | Three identical REF2VA clips: baseline, H3 8-step Turbo LoRA at strength 1, baseline again. LoRA changed video (max abs 0.765625) and audio (0.140625). Both baseline video/audio tensors are exactly equal across the intervening patched clip (max abs 0.0), proving effect and sibling isolation for this setup. All tensors finite. |

Local full job history: `.validation/optional-providers172-results.json`. Small synthetic image fixtures validate execution contracts, not perceptual interpolation quality.

The matching control used no SLA node and moved text encoding to CPU. It does not establish why the earlier process disappeared, nor certify other attention/allocator combinations. Native elapsed time was 78.64s and Master 177.02s; these are not a fair speed benchmark: the Master additionally performed initial model-file hashing, VAE decoding, cache writing and assembly, while the native control saved latent tensors only.

The live registry also passed 25 explicitly checked compatible connections, 27 unique public IDs/display names, and seven categories. Fresh production UI mode switches passed in both directions for Settings, SelfLift and the local prompt model. Screenshot: [corrected SelfLift](audit-images/selflift-controls-1.7.3.jpg).

Follow-up defects found during inference: model-file hashing happened before the active clip was announced and even during approved replay; it now runs after the preparing event and is skipped for approved/source replay. Learned and sampler-based refinement could report `refine: off` despite `refined: true`; the fallback report now says `applied`. Both follow-ups have regression coverage; their deployment verification is still pending while inference jobs run.

All four enhancement fixtures produced finite video/audio tensors. Learned upscale and global refinement preserved first-pass audio exactly; sampler-backend refinement changed audio along with video. The backend tooltip now makes this distinction explicit. SelfLift used three first-pass steps versus the one-step control, so its changed audio is not treated as an isolation failure.

## GPU failure evidence supplied by the user

The supplied September 14 log records explicit interruptions during initialization, successful eight-step runs, and then a fatal `c10::AcceleratorError`: `CUDA_ERROR_INVALID_VALUE` from `cuMemFreeAsync`. The Python stack runs through the SLA attention plugin into `comfy_kitchen.backends.eager.sol_attn`. It proves that particular process aborted in the CUDA allocator/attention path, not that the Master raised an ordinary Python error. It does not establish the ultimate cause, nor can its different timestamps/prompt IDs be equated with the October validation jobs.

The currently running server reports PyTorch 2.14.0+cu130, comfy-kitchen 0.2.33, comfy-aimdo 0.5.3, `--use-sage-attention`, and cudaMallocAsync. No host allocator/attention launch flags have been changed during this audit.

## Remaining required evidence

- Production dimensions and quality. The completed mode/continuity/LoRA fixtures cover execution and tensor contracts, not final-quality production output or every model/sampler combination.
- Face model and Semantic Bridge inference; SDK-capable RTX frame generation. Detector folders and RefMod library currently list no installed models, the local LLM list has no model, and Semantic Bridge exposes its missing-weight placeholder.
- Matched runtime, peak VRAM/RAM measurements and real vision proposal/appearance accuracy.
- Production-size/quality and performance comparisons remain distinct from the successful tiny functional fixtures.

These remain open, not passed by inference. Missing model/SDK dependencies and the unresolved native initialization outage are concrete limits on end-to-end certification.

## Follow-up execution and corrections — 17 October

- Next-unapproved job `699bff71-6f7d-4b60-abba-0cc85ace6571` restored the approved predecessor and generated only the unapproved next clip. All-approved job `92e06950-b7ac-4ab3-ab57-512b679585ab` returned all three cached clips, generated zero, without a diffusion model connected.
- Actual Full Preview encoding from that project included all three completed clips, no missing IDs. Downloaded MP4 decoded as 15 frames, 128×128 at 24 fps.
- Continuity job `f6f8d9d9-0c17-4778-be16-c64e2795d733` completed Motion Context, Latent Carry and Tail Handoff. Each pair used five-frame base clips. Motion/latent produced ten-frame decoded takes with five borrowed frames removed, leaving five new frames each. Tail Handoff produced five frames and removed one repeated boundary frame during contiguous assembly. Six clips therefore assembled to 29 frames, consistent with the current one-frame handoff contract. This does not measure visual seam quality.
- Cache/model override job `b88a942f-7a72-4272-a66f-bd6a70f74833` completed baseline → cached override → baseline. Actual cache log reported 4/6 skipped block-stack evaluations. At deliberately aggressive threshold 1.0, cache changed video/audio (maximum differences 1.6346171 / 0.8547031); the two unpatched baseline clips remained exactly equal for both streams. All tensors finite. The theoretical skip ratio is not an end-to-end speed benchmark.
- Tail From Latent incorrectly reported five frames as 0.2083 seconds while returning only 0.2 seconds of native decoded audio; short decoded videos could also report more frames than present. A failing real-tensor regression reproduced both cases. The fix fits audio to actual decoded video before slicing and caps the aligned count to available frames.
- Corrected stale manual descriptions of blue/purple overlays to the actual background-free chain icon and its seconds tooltip. Documented the one-frame Tail Handoff assembly reduction.
- Full local rerun after these fixes: 223 backend tests and 40 real CPU tensor/media/provider checks passed. All six JavaScript suites passed for the final release.

Release 1.7.4 code commit `c90534403f7bb410419362b693de25fc0478ed7c` pushed and deployed. The runtime status endpoint confirmed loaded_version 1.7.4 and 27 nodes after the idle-queue restart. No current job was interrupted and no allocator/attention launch flags were changed.

Deployed follow-up checks:

- Tail VAE job `27554f81-a942-46c8-bfc9-8041a2ca85ca` returned five frames and 0.20833333333333334 seconds. Actual saved FLAC decoded as 6,667 samples at 32 kHz, exactly round(5/24 × 32000).
- All-approved replay `e9a76e4b-a0ed-4851-8e1c-710b631e27f1` after restart: generated zero, restored three cached clips, output 15 frames, no diffusion model connected.
- Native VIDEO integration `37e0db1e-fce6-403d-9852-2b3a4acbefbe`: stock CreateVideo → Reference Pack VIDEO input → Master existing-video clip completed; five source frames, zero generated. The fixture initially omitted the required CLIP input; that test graph was corrected, without changing the product schema.
- Learned pixel upscale ran as the valid output branch of `7aba1a08-b8c9-4967-a304-73ac26f745be`, using installed RealESRGAN_x4plus. Saved PNG verified 256×256 from a 128×128 fixture. The subsequent native-video job reused that output cache.
- Fresh live browser: empty Reference Pack compact layout inspected at readable 86% zoom; export picker appeared for clip_ids and disappeared again for all. Screenshot: [Reference Pack](audit-images/reference-pack-empty-1.7.4.jpg). All 27 node default layouts had already been inspected in the earlier pass; this pass rechecked changed panels.
- Task-owned audit workflow tabs were closed without saving layout changes. User workflow tabs preserved. Temporary Node browser proxy stopped and absence confirmed. One-shot API helpers exited.

Remaining items above are explicitly unverified or dependency-blocked. This release does not certify production-size performance, perceptual quality, every parameter combination, or the missing model/SDK paths.
