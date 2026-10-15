# Server validation — 15 October 2026

Runtime revision: `8c0a796899c79fb881105bb8829520ef46513bc0`, package 1.6.0.
ComfyUI 0.35.1, PyTorch 2.14.0+cu130, RTX 4090. Test graphs were independent API jobs; the user's canvas was not edited.

| Check | Result |
|---|---|
| Backend regression suite | 204 passed |
| Real CPU tensor/media suite | 36 passed |
| Editor, authoring, preview, preview-node, documentation suites | All five passed |
| H3 VAE decoding + Lanczos Letterbox Fit | Success; five 128×96 outputs from a 64×64, five-frame empty native AV latent. First image has exactly 16 black pixels of padding on each side and nonzero centre pixels. |
| Refine configuration on server | Exact `18446744073709551615` seed preserved; memory reserve 35%, guard direction and independent seed policy returned correctly. |
| Opt-in automatic H3 upscaler acquisition | Installed canonical checkpoint passed size/SHA-256 verification and resolved to its filename. No weight download was necessary. This does not test learned-upscaler inference. |
| Project Import configuration | Tritant sampler_name translated to euler, steps=3 and 320×192 manual canvas on the Config output. |
| Raw cache restoration and All Clips | Two synthetic native H3 AV cache segments restored as approved. No diffusion MODEL connected. Master decoded both with real video/audio VAEs, returned 10 frames, generated=0, and reported both actions as cached. |
| Next Clip and Latest decoded retention | Same two approved takes, generated=0, five output frames, decoded_output=latest. |
| Full Smart Preview after Latest output | Both cache IDs present, 2/2 completed clips, missing_clips empty. |

## Sampling comparison boundary

A separate native-versus-Master comparison was submitted with the same FL2VA checkpoint, prompt, seed 8675309, Euler/simple, CFG 1, shifts 12/3, three steps, 320×192 and 22 frames. The last observed progress was native model initialization after text encoding. The endpoint then timed out and returned Cloudflare HTTP 502. No comparison tensor artifacts could be recovered. The cause was not established; this is not evidence of output equivalence, a memory benchmark, or a confirmed package regression. The server was recovered and the smaller tests above completed afterward. No new diffusion comparison was queued after recovery.

The successful cache replay used synthetic native latent fixtures, not a quality comparison of generated video. It proves storage, approvals, decoding, assembly and preview visibility across the real server contracts. It does not establish generation quality or performance superiority over the three source projects.

Server test jobs: media `06ff7f8f-d54d-4356-a79c-a99162cf5609`; All Clips replay `60df70b9-52bb-4585-9df3-50557f2db77e`; Next Clip replay `59459438-4607-4c58-95ca-b44674e61719`. Server outputs were written beneath `validation/parity16` and the replay project uses an isolated content-derived project ID.

All inspection scripts were one-shot processes. No temporary Node proxy remains running. The final generation queue was idle.
