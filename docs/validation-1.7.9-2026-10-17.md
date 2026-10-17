# Final phased memory cleanup 1.7.9

Extends the measured continuity-wrapper improvement to every ordinary sampling-to-decoding boundary, including the first independent clip. Native model residency is released while execution-scoped wrappers remain alive for reuse. Reviewed first-pass and per-refine-pass video caches also stage pixels before audio work. This uses ComfyUI's targeted unload API, not global model unloading or third-party file changes.

Validation before deployment: 236 backend tests, 19 real tensor/media tests, and all six JavaScript suites. Prior 1.7.7 Full raw-output and 1.7.8 Latest raw-output runs each successfully generated all four ten-second clips at 1280x736, two steps. The final-release runtime test and approved/export checks follow below.

## Reference video megapixel verification

Reran the real CPU tensor checks for graph/file preparation, the 0.5 MP default and explicit Off, and the Master native-conditioning contract for REF2VA and RV2V. All three passed. Inspected the installed native MiniMaxH3ReferenceToVideo implementation: its reference-video canvas branch preserves smaller inputs before VAE encoding; it does not scale them to the generation canvas.

A CPU diagnostic using a decoded frame of the actual injected reference video and the deployed pool preparation measured 640x640 input. At 0.25 MP, the pool and Master model_frames were both 480x480 (230,400 pixels); at 0.5 MP, both were 640x640 (409,600 pixels). In both cases model_frames shared the prepared pool tensor's data pointer. Thus 0.5 MP does not shrink this particular video because it already fits the budget. This diagnostic did not intercept the active GPU run; the conditioning handoff is separately covered by the contract test and installed native source inspection.

## Final deployed GPU and media checks

Deployed code commit: `10738b93734b58840defd505cb75193c6ea54b48`, loaded release 1.7.9. All-clips job `d4ca7e89-186e-48a2-ac9b-b4b283ab65c4` succeeded in 632.302 seconds. Four ten-second REF2VA clips used the original prompts, seeds, assets, continuity, and 1280x736 output canvas, with sampling reduced to two steps. This is an execution/memory test, not a production-step quality benchmark. Clip progress events advanced through all four IDs and ended completed.

The 280 memory samples recorded process peak RSS/HWM 47.447 GiB, peak anonymous memory 45.553 GiB and peak swap 0.306 GiB. Before first-clip decode, anonymous memory was 20,260.7 MiB, versus 40,435 MiB in the preceding 1.7.8 run. Before subsequent decodes it stayed around 26,360–26,526 MiB. Overall process peak remains substantial during sampling; this does not claim all high-resolution workloads fit. No restart or OOM occurred. Sampling video and audio latents were bit-for-bit identical to the 1.7.8 test for all four clips (maximum absolute difference zero).

Approved-clip rerun `8087e039-bfcd-43a5-a08e-a9c9cb052af9` succeeded in 2.398 seconds. All four generation IDs and trim metadata remained unchanged. The Master executed while upstream model/reference nodes were cached; no new take was generated.

Project export `0abb7631-908b-4071-957d-329dad7d20cb` succeeded in 8.959 seconds. A forced second export with a different filename prefix, job `3dcd43bb-665d-4d89-9865-3aac3722c20c`, executed in 0.091 seconds. All four encoded segment paths and nanosecond modification timestamps were unchanged, proving segment reuse rather than merely a cached node result.

PyAV fully decoded both resulting videos: the Latest raw-output encode contained 243 frames at 1280x736/24 fps; the assembled project contained 962 frames at 1280x736 (nominal 24 fps, MP4 average reported 24.00078). Both had a decodable audio stream with all samples finite. The Latest raw-output setting did not prevent all four clips from generating or the full project from exporting.

The remote memory monitor finished without errors. All task-owned local generation/export controllers exited. The final ComfyUI queue was empty. Third-party source files were not modified.
