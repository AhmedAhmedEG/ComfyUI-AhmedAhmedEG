# Master generation pipeline audit — 12 October 2026

This audit compares the current editor's serialized values with Master execution, native conditioning calls, sampling, cache reuse, and output assembly. It uses controlled ComfyUI/model substitutes for execution contracts and real CPU tensors/audio/FFmpeg for media checks. It does not certify H3 checkpoint quality, GPU memory usage, or third-party detector/adapter weights. The running server was not changed or restarted during this audit.

## Problems corrected

1. **Accepted clips were reconditioned before cache reuse.** Current references and model overrides were validated, native conditioning was built, and Latent Carry could alter the preceding output before the accepted result was loaded. Approval now branches to saved artifacts first. Complete saved media needs no current reference or sampling model. Missing media may be decoded from its saved latent under the same take ID. Repairing missing Keep Source Audio still requires the original source soundtrack. Saved prefix/tail trimming metadata is applied when assembling accepted clips.
2. **Lazy loading ignored execution scope.** It requested model families for accepted clips and later clips that Next Clip would never generate. Lazy planning now uses the same timeline migration and approval rules as execution, and stops at the first eligible generated clip in Next Clip. All Clips loads the families needed for its eligible clips.
3. **The Master's direct output treated the first clip's canvas as authoritative.** Later results were resized to it and could be distorted. Assembly now chooses the maximum enclosing width/height and fits each clip proportionally with black padding, matching Smart Preview's mixed-canvas policy. Individual cached takes keep their own original dimensions.
4. **Clip Audio offered invalid combinations.** Existing footage offered Generate although it is passed through without sampling. Non-source clips offered Keep Source Audio although they have no source video. The selector now exposes applicable choices. Invalid serialized policies fail before sampling.
5. **Semantic Bridge could silently do nothing.** Missing weights and rewrite exceptions returned unchanged conditioning. A connected bridge now reports a failure instead; an explicitly disabled pack remains a deliberate bypass.
6. **Generation highlighting started too late and handled the wrong event shape.** The clip is now marked before conditioning preparation, through sampling. ComfyUI's executing event supplies a scalar node ID; nonterminal scalar/object IDs must not clear the marker. Completion, terminal null, interruption, and errors clear it. The Editing text badge is removed; the gold outline identifies the inspected clip.

## Control-to-execution matrix

| Controls | Actual use | Evidence / limits |
|---|---|---|
| Next Clip / All Clips | Generate the first eligible unapproved clip / every eligible unapproved clip. Accepted clips reuse saved results. Locked footage is passed through. | Scheduling, seed order, approval, missing-cache, lazy-family and Full Video cache-order regressions. Next Clip's direct Master output stops at its generated clip; Smart Preview Full Video independently reads all available timeline takes. |
| Conditioning Only | Builds native conditioning and starting latent without diffusion sampling. It does not complete subsequent clips or invent their generated continuity. | Native routing and guide-output tests. |
| Clip type and RefPack assignment | Fixed task type selects the FL2VA or REF2VA native family. Selected IDs resolve from the injected pack; source video is bound once. | All nine editor choices and backend asset contracts tested; invalid media types/counts fail before sampling. |
| Existing Video | Uses selected video frames/audio and range; no diffusion sampling. A smaller model-input copy supplies context to a later generated clip. | Actual CPU trim, paired sound, frame-rate normalization, cache and preview tests. |
| T2V / I2V / FL2V / L2V | Text-only, opening image, opening/ending pair, ending image respectively. Allowed previous-clip continuity can supply the opening frame. | Native payload and required-asset tests. |
| REF2V / V2V / RV2V | Generic multimodal references; source-video guidance; source plus extra references respectively. V2V/RV2V route through native ReferenceToVideo. | Source slot order, asset limits, input budget and source audio routing tested. These are reference-conditioned generation, not a guaranteed pixel-identical edit. |
| Image Inpaint | One-image/five-frame native pass, exposing its last frame as a still. | Output contract tested. This mode has no mask input and is not masked region inpainting. |
| Clip duration | Converts seconds to the H3 24 fps frame grid; generated lengths align to 5 + 17n. Video edits instead use the decoded source range. | Native lengths, source range and prefix-trim tests. Requested seconds may round up to the supported grid. |
| Seed / Fixed / Randomize / Increment / Decrement | Seed reaches noise preparation/sampler. Completed clips alone advance their saved next seed, wrapping uint64. Accepted clips retain their take. | Seed persistence, uint64, wrap and clip-by-clip tests. |
| Raw/structured/shared prompt and placement | Backend compiles task-specific structured fields and adds shared text according to prepend/append. | Prompt compilation, aliases and sampler-path prompt tests. |
| Independent | No previous-clip guide/carry. | Payload and numerical bypass tests. |
| Motion Context | Previous decoded tail becomes a native guide; audio tail is independently sliced and capped to available video context. Borrowed prefix is trimmed from delivered output. | Native guide payload, audio slicing and prefix tests. |
| Latent Carry / Redraw Strength | Previous AV latent or encoded pixel tail fills the prefix; video/audio masks implement pinning and redraw. | Real CPU copy/mask tests and Master argument assertions. Visual continuity quality requires an H3 run. |
| Tail Handoff | Uses one final image; no motion guide or borrowed audio. | Native argument and trim tests. |
| Video Input Resolution | Native/custom short-edge/megapixel budget controls model-input frames. Original cached footage and generated canvas remain separate. | Tensor dimensions, 32-pixel alignment, no-upscale and source tests. It does not reduce the generated latent canvas by itself. |
| Clip Audio | Generate keeps generated sound; Keep Source Audio chooses source sound; Mute emits correctly sized silence. Existing footage preserves source sound or mutes it. | Source/edit, silence and invalid-policy-before-sampling tests. Changes apply to a newly processed clip; approval accepts existing saved media until unapproved. |
| Join Fade / Match Audio Gain | Finishes assembled waveforms after sampling, with no frame overlap. Zero fade disables edge ramps. | Master argument assertions and real waveform/preview tests. Different from Audio Context and latent Seam Redraw Strength. |
| Clip model override / LoRAs | Selects a named model and applies enabled adapters per clip without leaking to later clips. | Missing override, adapter strength, file signature and model isolation tests. Actual adapter quality is untested. |
| Interior guides / grading | Guide time maps to 24 fps plus the borrowed prefix. Exposure/contrast/saturation edit decoded frames. | Existing guide, reference and grading routines audited; CPU media helpers tested. H3 response to guide contents remains model-dependent. |
| Sigma shifts / steps / CFG / sampler / scheduler / external sigmas | Values reach native AV model shift and sampling calls; external schedules are validated. | Direct argument assertions, tensor sampling contract and invalid sigma tests. |
| SelfLift / Refine / FaceRefine / Semantic Bridge | Connected packs select their corresponding execution passes. Current pass settings reach their implementation. | Controlled pass routing tests, existing tiling/refine numerical tests, and explicit missing-bridge failure test. Real optional weights, GPU execution, detector quality and performance remain unverified. |
| Project save/open, approval, preview, zoom/timecode | Project/cache identity persists; preview reads saved takes. Zoom/timecode and clip name are authoring controls, not sampling parameters. | Server project, editor persistence, readiness and preview tests. |

## Verification and operational state

The backend suite now contains **160 passing tests**, including ten new execution regressions. **16 real CPU/media tests** pass. All ten new regressions were also run using real PyTorch tensors and filesystem caches, with controlled model calls. Editor, preview and preview-node checks pass. These results validate parameter routing and media behavior, not model output quality.

The fixes are prepared locally. The user is generating on the server and explicitly requested no restart; the live installation must remain untouched until that run is finished and deployment is resumed.

The event-shape check uses the [official ComfyUI frontend API source](https://github.com/Comfy-Org/ComfyUI_frontend/blob/main/src/scripts/api.ts), whose executing event detail is a serialized node ID. Tests exercise both that scalar form and the older object form.
