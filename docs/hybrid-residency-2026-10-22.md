# Hybrid H3 residency test — 22 October 2026

## Result

The native hybrid configuration works functionally on installed ComfyUI 0.42.3 / comfy-aimdo 0.5.6: H3 uses `ModelPatcher`, while the text encoder and both VAEs use `ModelPatcherDynamic`. Both two-clip All clips submissions succeeded. H3's base and shifted/LoRA configuration identities were reused across clips and submissions. This does not establish quality parity or a performance improvement.

## How it ran despite the image entrypoint

Docker exec launched an independent, temporary Python process inside the existing ComfyUI container. Its own arguments enabled Dynamic VRAM and bound only 127.0.0.1:8189. The image entrypoint continued running the production listener on port 8188 with `--disable-dynamic-vram`. No image rebuild, entrypoint edit, production restart, third-party source edit or publicly installed test node was required.

The diagnostic bootstrap registers two classes only in its own process after native node import. Its test H3 loader calls `comfy.sd.load_diffusion_model(..., disable_dynamic=True)` directly. It never loads a dynamic H3 and converts/reloads it afterward. Native LoRA and SLA nodes consume this MODEL normally. A probe asserts the memory-manager type of H3, CLIP, VideoVAE and AudioVAE before generation. The test uses a separate user directory so its successful server's logs and settings are isolated.

Initial harness startup attempts exited before submitting a generation because of bootstrap argument/import ordering and directory setup; they were corrected. They are not counted as failed model tests.

## Test case and evidence

Two independent REF2VA clips, 320×192, native-aligned 56 frames each, two Euler/beta steps, two selected image references and the existing clip-local Turbo LoRA. The second submission changed only seeds. The private project ID is `codex_hybrid1720`; the user's workflow and project were not edited. The small sequence is below the configured SLA threshold, so this is not an active sparse-attention or full-resolution benchmark.

| Submission | Prompt ID | Result | Wall time including polling |
| --- | --- | --- | --- |
| Initial All clips | `cde3bed8-99ef-40cf-9e82-107d85f6834c` | success | 445.86 s |
| New-seed All clips reroll | `2bfffd57-3d69-4b08-ac64-506a20e5a08c` | success | 93.54 s |

H3 base ID was `140468048855552`; sampling configuration ID was `140451087488720`, reused across both clips and both submissions. These identity checks prove reuse, not the absence of every native temporary or backup allocation.

At the initial run's last audio-decode boundary, the native log reports 14,709.72 MiB of H3 remaining loaded after partial eviction. At the reroll's final video-decode boundary, 16,180.13 MiB remained. This is partial retention with automatic pressure-based cleanup, not permanently pinning the entire H3 model. Host process swap was 0 MiB at recorded completion boundaries; peak RSS was approximately 48,603 MiB.

After the reroll, the test called the pack's manual memory-release endpoint while idle. NVIDIA-reported GPU usage fell from **20470 MiB to 726 MiB before process shutdown**. This verifies that the manual control clears the mixed-mode model/loader handles. It does not delete saved results.

## Important limitations

- There were **364 native `Pin error.` warnings**. Installed `pin_memory()` emits this when `cudaHostRegister` fails, clears the CUDA error and returns False; the caller leaves the weight unpinned in host RAM. Both generations completed through this fallback. The registration failure's underlying cause is not established. It is host-memory pinning, not proof of a GPU out-of-memory error, and not proof of output corruption.
- The hybrid warm run took 93.54 s. The earlier all-static-manager smoke test took 34.61 s for its warm run. These were not contemporaneous matched A/B runs, so no exact slowdown ratio or single cause is claimed. There is no demonstrated speed advantage that justifies switching production.
- Before this test, NVIDIA reported roughly 19 GB used even after the idle production cache was cleared, while a fresh CUDA process reported roughly 20 GB free. Usage later dropped during the test. The initial timing is therefore confounded by changing memory pressure/reporting; no owner or definitive cause was established. Local Windows GPU diagnostics were not used as evidence for this remote GPU.
- Full-resolution, continuity, different adapter stacks, image-quality equivalence and long-run stability are not established by these two smoke submissions.

## Cleanup and deployment decision

The test process and runner have exited. The final check found no remaining diagnostic processes. GPU usage after shutdown was `174, 22435, 0` (MiB used, MiB free, utilization %). Production remained healthy and idle with the original entrypoint arguments:

```text
python3 ./main.py --disable-dynamic-vram --use-sage-attention --listen=0.0.0.0 --port=8188
```

No production node or global memory policy was changed. If adopted later, the per-model decision belongs at an H3 loader using the native load-time flag, outside Master. Global Dynamic VRAM would be enabled, and only H3 would select traditional caching. The pin-registration behavior and a controlled performance comparison should be resolved before shipping that as the recommended setup.
