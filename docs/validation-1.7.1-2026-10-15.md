# Implementation validation — 1.7.1

Revision tested: `0c59a4d5f0e6b70cf4e06f7e3e135b12fd4bdef7`, 15 October 2026. This is a fresh validation run, separate from the earlier 1.6/1.7 evidence. No implementation changes or deployment were required by the passing checks below.

## Completed checks

| Layer | Fresh result | What the evidence establishes |
|---|---|---|
| Backend regression suite | 216 passed | Mode/endpoint and selected-reference routing, continuity policy, seed/config propagation, approvals/cache reuse, invalidation, imports, per-clip LoRA isolation, refinement controls and authoring contracts. Many pipeline cases use mocked native components; these are not diffusion-quality tests. |
| Real CPU tensor/media + provider suite | 38 passed | Pixel resizing and aspect handling, tensor continuity operations, real audio/video encode/decode and preview/export behavior, Spike Guard numerical behavior, plus two HTTP/SSE provider protocol checks. |
| Browser DOM suites | All six passed | Timeline editing/migration, persistent timecode/zoom/seeds, authoring and multiple-role checkboxes/cards, preview switching/cleanup, documentation links, transfer progress/errors/cancellation. These run against a DOM harness, not the user's live canvas. |
| Deployed runtime | 1.7.1; 27 node types | The current backend was loaded on the server. |
| Live foreign workflow import | Passed | Recovered history, people boxes, reviewed card and explicit model alias through real server routes. |
| Live portable export/import | Passed | Media archive, boxes, cast card and historical prompts round-trip through the deployed routes. |
| Live transfer progress | Passed | Job-scoped Conversion complete, Packing media and Extracting media websocket phases received. |
| Live imported history review | Passed | Produces a review draft and warning, without silently marking historical reference labels verified or approving the clip. |

The CPU face-refine test exercised the no-face fallback, not successful face detection/tracking/stitching with production weights. HTTP provider checks use a deterministic fixture; they do not measure a real vision model's understanding. The deployed local `models/LLM` folder has no configured model.

Commands run:

```powershell
.validation/Scripts/python.exe -X utf8 -m unittest discover -s tests
.validation/Scripts/python.exe -X utf8 -c "import faulthandler,unittest; faulthandler.dump_traceback_later(45,exit=True); unittest.main(module=None,argv=['checks','validation.test_numerical','validation.test_media_codec','validation.test_continuity_numerical','validation.test_pack_source_numerical','validation.test_parity_numerical','validation.test_smart_preview','validation.test_forge_provider_http'])"
node validation/test_editor.cjs
node validation/test_authoring_tools.cjs
node validation/test_preview.cjs
node validation/test_preview_node.cjs
node validation/test_user_guide.cjs
node validation/test_transfer.cjs
```

Python temporary directories were placed under `.validation/test-temp`. Live fixture runner: `.validation/verify_validation171.mjs`; saved route results: `.validation/parity17-server-results.json` (reports 1.7.1).

## GPU sampling failure

Preflight: ComfyUI 0.35.1, frontend 1.51.10, Python 3.12.14, PyTorch 2.14.0+cu130, RTX 4090, 21.0/22.5 GB free VRAM and 49.7 GB free system RAM. The queue was empty. The test used an isolated API graph; the user's canvas was not edited.

The comparison used the installed FL2VA pruned int8/convrot checkpoint and Qwen3VL text encoder, identical prompt and seed `8675309`, Euler/simple, CFG 1, shifts 12/3, one step, 128×128 and five frames. Native sampling and the Master were to save separate video/audio latents for numerical comparison.

Job: `0d5c4e51-031a-41a6-999a-7a885f21e563`. Graph and job metadata are saved locally as `.validation/gpu-validation171-workflow.json` and `.validation/gpu-validation171-job.json`.

The last reachable log was the **native control sampler** at `0/1`, `Model Initializing`, after staging the MiniMaxH3 model. The endpoint then returned HTTP 502, followed by HTTP 530. The Master branch was not observed executing. No completed comparison artifacts were collected. An MCP restart attempt could not reach any Manager reboot endpoint and did not restart the server. Host-side ComfyUI/tunnel recovery was requested.

This repeats the earlier failure stage with a much smaller graph. It does not establish OOM, the cause of the outage, a Master regression, output equality or inequality, or successful GPU sampling. The sampling setup needs host-side failure logs before further heavy comparison tests.

## Recovery and additional live checks

After the user requested a connection retry, the endpoint was reachable again, with a fresh startup log and an empty queue. The interrupted diffusion job had no history record. No repeat of the failing diffusion graph was submitted.

| Recovered-server check | Result |
|---|---|
| Real H3 VAE decode and Lanczos Fit | Passed: five frames; saved image 128×96; exactly 16 zero-valued pixels of side padding and nonzero centre content. |
| Refine controls and installed upscaler resolution | Passed: exact uint64 maximum seed, independent policy, guard direction, 35% memory reserve and canonical installed upscaler filename. This resolves/verifies weights, not learned-upscaler inference. |
| Imported sampler configuration | Passed: Tritant settings emitted Euler/simple, steps 3, manual 320×192. |
| Raw native AV cache restoration and All Clips | Passed: both synthetic saved takes restored as approved; Master returned ten decoded frames, both actions cached, generated=0, with no diffusion model connected. |
| Next Clip with Latest decoded output | Passed: both takes still cached, generated=0, five returned frames. |
| Full Smart Preview | Passed: both clip IDs available, 2/2 completed, missing_clips empty. |
| Runtime and combined roles after recovery | Passed: backend 1.7.1, 27 types, combined character/place/style import and updated served frontend. |
| Final queue | Empty; server reachable. |

Jobs: VAE/config `c0249865-d161-4e03-8fc8-de145e5d333b`; approved replay `43c44d30-42cf-46c5-9187-32cebd9e0310`; Next Clip/latest `b501f36c-9608-4674-b594-81304025982d`. Local evidence: `.validation/gpu-media16-history.json`, `.validation/gpu-import16-history.json`, `.validation/gpu-latest16-history.json`, `.validation/gpu-preview16-plan.json` (these reusable fixture filenames now contain this run's job results).

The saved cache tensors are synthetic native-format fixtures, not generated footage. These successful jobs validate real VAEs, approval/cache reuse and preview assembly; they do not close the diffusion comparison or optional-model quality/performance gaps below.

## Validation still outstanding

- Successful native-versus-Master diffusion outputs and numeric comparison.
- Production-size generation and end-to-end per-clip LoRA output comparisons.
- Full GPU SelfLift, learned latent upscale, tiled/refine passes, face refinement, Semantic Bridge and optional RTX provider checks.
- Peak GPU/system memory and elapsed-time measurements under matched workloads.
- Actual Find People and appearance-card accuracy using a configured vision model.

The local and live-route passes establish substantial functional coverage. They do not justify describing all implemented features as fully GPU-validated or claiming quality/performance parity with the source projects. No temporary persistent proxy/helper was started for this run; invoked Node scripts were one-shot processes and exited.
