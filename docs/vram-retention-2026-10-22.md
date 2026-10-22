# H3 GPU retention investigation — 22 October 2026

## Implemented and deployed

Release 1.7.20 removes our additional AIMDO cast/prefetch/watermark cleanup at each clip boundary. Temporary output tensors are still released; ComfyUI retains ownership of execution-end cleanup and memory-pressure eviction. This follows Extender's full-run behavior, without patching ComfyUI or any third-party custom node.

Master → Project → Clear VRAM requests the native queue worker's `free_memory` operation. It releases the pack's active configuration and CPU adapter reuse, unloads native models and resets native execution-cache handles. Resetting those handles matters when a native loader itself owns GPU weights. It never deletes project files, saved clip results or the reference-latent disk cache. Busy or pending generation returns HTTP 409; no interrupt is sent. The next generation reloads its required models.

## Online research and installed source

The official [startup flags](https://github.com/Comfy-Org/docs/blob/main/development/comfyui-server/startup-flags.mdx) and [CLI implementation](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy/cli_args.py) expose `--highvram` for GPU retention. `--disable-smart-memory` has the opposite purpose: it aggressively offloads models. The production server was already using smart memory.

In the installed ComfyUI 0.42.3, both `--highvram` and `--disable-dynamic-vram` select the estimate-based ModelPatcher rather than AIMDO Dynamic VRAM. The latter leaves normal smart-memory eviction enabled, allowing H3 to yield space for the text encoder and VAEs. `--highvram` additionally changes H3's offload device to the GPU. These are server-wide startup choices, not per-Master options; changing globals inside a node would not safely change patchers created by upstream loaders.

## Isolated native-cache trial

A temporary listener bound only to 127.0.0.1:8189 used `--disable-dynamic-vram`. The production listener and its launch configuration were unchanged. The test runner stops its temporary listener automatically and checks the production queue during generation.

Two independent REF2VA clips, 320×192, 56 frames each, two Euler/beta steps, two selected image references and the existing clip-local Turbo LoRA were generated with All clips. Both clips were then rerun with different seeds. This is a memory/functional smoke test, not a full-resolution quality or SLA benchmark: the sequence is below the configured SLA threshold.

| Run | Result | Wall time, including polling | GPU memory after idle |
| --- | --- | --- | --- |
| Cold two-clip run | success | 272.78 s | 19,786 MiB |
| Two-clip reroll | success | 34.61 s | 19,722 MiB |

Before the test, total GPU use was approximately 1,302 MiB. After the second clip in the reroll, the native log reports 13,570.12 MiB of H3 still loaded after making room for AudioVAE. Torch allocated memory was 19,121.8 MiB, including other managed models/buffers. This is physical-residency evidence, unlike merely observing the same Python model object. It does not mean the entire 19,996 MiB H3 model remains on GPU.

The cold/warm difference includes checkpoint initialization, LoRA patching, reference preparation and file caches; it is not a measured speedup over the production Dynamic VRAM mode. Host process swap reached approximately 1,203 MiB, so the test does not establish that this mode eliminates host-memory pressure.

Test prompt IDs: `b7b71bb6-22d3-4357-b19b-25df92b5ea0b` and `8d5f9634-13aa-4da4-868d-95e02e561687`. Isolated projects use `codex_retention1720_*`, never the user's project.

## Strict high-VRAM trial: do not select

The same graph was submitted to a separate temporary process with `--highvram`. Before the first clip's decode, Torch reported 39,860.9 MiB allocated and 41,504 MiB reserved on the CUDA device. Physical dedicated use reached about 22,449 MiB, with only 160 MiB free. On this WSL/Windows system, device allocations can spill into shared/system memory; the 39 GB figure is not physical dedicated VRAM. Host process swap reached about 3,630 MiB.

Its first two-step sample took 22.6 seconds, compared with approximately 0.3–0.6 seconds in the normal native-cache trial at this tiny resolution. During the first clip's VAE stage the test listener became unresponsive to a bounded HTTP request. The harness recorded a timeout and terminated only its temporary process. An attempted interrupt of that test listener received a connection reset as the harness shut it down. No completed two-clip high-VRAM result or quality comparison is claimed; there was no production-server crash.

The trial therefore does not justify enabling `--highvram`. Native GPU/offload/backup allocations can exceed card capacity even though our pack retains only one active configuration. This is a concrete reason to prefer pressure-aware retention over indiscriminate GPU pinning.

## Deployment and remaining decision

The node-pack changes are pushed and deployed. The Linux regression suite passed 153 tests; the focused memory tests, editor behavior tests and generated guide checks passed. The new control's rendered layout was inspected in a browser fixture, and its deployed endpoint returned HTTP 200 while idle.

Permanent startup configuration has not been changed. Automatic approval review rejected editing `/entrypoint.sh` without approval for that specific server-wide change. If selected after reviewing the tests, the exact change is appending `--disable-dynamic-vram` to the existing ComfyUI command; retain `--use-sage-attention`, listen address and port, and do not add `--disable-smart-memory`. Back up the launcher first. Removing the added argument restores the current mode. The flag is version-specific and the installed server warns that it may be removed in a future release.

The small test establishes retention, not full-resolution performance or quality parity. Avoid promising permanent full-model residency on a 24 GB GPU with a roughly 20 GB H3 model, 15 GB text encoder and 5 GB VideoVAE.
