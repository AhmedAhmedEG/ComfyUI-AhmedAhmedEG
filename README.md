# ComfyUI MiniMax H3 Master Director

Version **1.0.6** consolidates the MiniMax/video production features of
[DaSiWa](https://github.com/darksidewalker/ComfyUI-DaSiWa-Nodes),
[AIMixer](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director), and
[Tritant](https://github.com/tritant/ComfyUI_MiniMax_H3_Extender) into one Director.
[FEATURE_PARITY.md](FEATURE_PARITY.md) records the pinned sources, required union,
and subsystem choices. These choices follow code/API review; they are not GPU
quality or speed benchmarks. See [REVIEW.md](REVIEW.md) for validation evidence.

The Master’s **Preview** tab plays the **latest completed clip** by default.
Switch to **Full video** to review the completed sequence. Each scope has its own
cached H.264/AAC preview file; latest mode never downloads the complete video.
The player restores from saved shot caches, supports autoplay and Save preview,
and refreshes after a shot finishes. Preview is independent of the **Output**
selector and never changes what downstream export nodes receive. Previews are
scaled to fit 960 × 540; final export keeps its configured resolution.

## Install and start

There is one public **MiniMax H3 Master Node** name. The package has 22 distinct
user-selectable tools, organized by purpose; internal algorithms are not separate
nodes. The two core nodes are in `ComfyUI-AhmedAhmedEG/Start here`.
[NODE_GUIDE.md](NODE_GUIDE.md) explains the everyday and optional tools.
[Open the practical HTML guide](docs/MiniMax-H3-User-Guide.html): follow one
starter recipe, add a reference, build a second shot, review Latest clip and save
the result. Inline diagrams explain the connections and preview transfer scope.
Optional features are grouped by task with searchable instructions for all 22
tools. The current starter can be downloaded directly from the offline guide.
Rebuild with `python tools/build_user_guide.py`.
Saved UI workflows using the former Master Director type migrate on import.
API prompts should use `MiniMaxH3MasterNode` as their `class_type`.

Copy `MiniMaxH3Director` into `ComfyUI/custom_nodes/`, install `requirements.txt`
with ComfyUI's Python, and restart ComfyUI. The installed ComfyUI must provide
native MiniMax H3 ImageToVideo, ReferenceToVideo, AddGuide, SigmaShift and current
`comfy_api.latest` VIDEO APIs.

Load `workflows/MiniMax H3 Start Here.json`. It uses standard **Load Diffusion
Model** (FL2VA + REF2VA), **Load CLIP** (type `minimax`), two **Load VAE** nodes,
and **Create Video → Save Video**. Only the Master and Director Settings are
custom nodes in the basic workflow. The saved filenames match the current server’s MiniMax H3 models. Check the five selections, edit
a shot and upload references in the Master. Both diffusion models are lazy:
only the family required by the timeline’s shot modes is requested.

`MiniMax H3 Consolidated.json` adds optional advanced export nodes, muted by
default. The Master tracks standard loader provenance internally for saved-take
reuse. Unknown third-party loader/modifier paths retain conservative live-session
cache identity. Use the fresh starter after updating from 1.0.4; removed wrapper
nodes are intentionally no longer registered. See NODE_GUIDE.md for replacements.

After `git pull`, **restart the ComfyUI process**, then reload the browser.
Pulling files does not reload Python node registrations in a running server.
`/minimax_director/status` reports the loaded version and installation path;
version 1.0.6 reports 22 types and only `MiniMaxH3MasterNode` as the Master.
Old wrapper-based graphs will show missing node types; use the replacement
list in NODE_GUIDE.md or load the fresh starter. If `pyav` appears under
`bit_depth` in an advanced exporter, reload its supplied example after restarting.
Two model loader instances in the consolidated example load different model
families; they are intentional. Advanced graph tools are optional, under their
own menu category.

Generation is **24 fps**, with native **17k + 5** frames and canvases divisible
by 32. Requested generation durations round upward to that frame grid. Source
edits are trimmed back to their actual source ranges. Use Output Processing or
Project Video to control playback/export FPS while keeping audio timing explicit.

## Supported production workflow

- **Generation:** T2VA, I2VA, first/last FL2VA, closing-only L2VA, REF2VA with
  image/video/audio references, and source V2V/RV2V. DaSiWa's Image Inpaint uses
  one image in a native five-frame pass and returns one generated still.
- **Authoring:** generated/source shots, source preview, split at playhead,
  equal split, scene detection, merge boundaries, selection, per-shot prompts,
  exact 64-bit seeds, shared prompt and references, LoRAs with previews, named
  model overrides, timestamped native guides, and structured/free prompts.
- **References:** upload/drop/paste/replace, content-addressed assets, media
  playback and trim, real waveform handles, draggable crop preview, exposure/
  contrast/saturation, scaling/divisible crop, roles/descriptions, frame picking,
  embedded video V/A/V+A switching, and RefMod bundles/library descriptions.
- **Prompt Forge:** reviewed editable multi-shot drafts from local Transformers
  or GGUF, Ollama, or a compatible API, with optional vision. Drafts preserve
  context and require explicit apply. Changed source context invalidates a draft.
- **Continuity:** independent, endpoint handoff, native motion guides in every
  video mode, or phase-aware latent carry with redraw masks. Prefix/video/audio
  trim is shared by previews and cached exports. Importing an existing video
  creates locked Clip 0. Saved takes can be selected as checkpoints and advanced
  through an explicit graph gate.
- **Sampling/refinement:** AIMixer Euler-state SelfLift with lift/rho/pixel
  anchor/transition and low-resolution carry; validated learned 3D H3 latent
  upscalers; custom model/SIGMAS/multiple refine passes; DaSiWa memory-aware
  spatial/temporal tiling with a shared diffusion trajectory, endpoint re-encode,
  continuation repin and original audio. An explicit sampler backend is also
  available. Pixel-model and optional RTX VSR/denoise/deblur remain separate tools.
- **Face/conditioning:** tracked face crop, native joint-AV injection and masked
  stitch controls, Semantic Bridge with exact compatible weights, and optional
  model-scoped residual Cache. Missing optional dependencies produce errors;
  detected no-face clips are reported and retained.
- **Projects/output:** atomic per-shot takes, restart provenance, autosave/recover,
  lightweight cache reconnect, portable media packs, append/overwrite import,
  missing-file checks, completed-shot seed advancement, source/generate/mute
  audio policy, grading, watermarking, seamless loops and progress reports.
  Core UI controls support English, Chinese and Arabic; project data stays
  language-neutral. Technical identifiers remain in their canonical language.

## Connecting output and resume

The Master Node's first nine output slots keep their prior order. `video` remains
VHS_VIDEOINFO metadata; `project_state` is the appended tenth STRING output.
LATENT is the final sampled shot, before decoded grading/face edits.

Connect IMAGE/AUDIO/FPS to Video Combine for previews and codec export. Video
Output creates a native VIDEO object. Connect `project_state` to Project Video
for cached disk assembly, individual shots, selected/all output, pre-refine
inspection or original-source output. Project tools can create this connection.
Disk assembly loads one cached shot at a time; the Master IMAGE preview still
materializes its selected sequence in memory. Temporal refinement stages its
complete output/noise in host RAM and enforces a memory budget.

Video Combine provides PyAV hardware/software codec selection, MP4/MKV/WebM,
H.264/H.265/VP9/AV1, actual 10-bit input, animated WebP/AVIF, requested audio
codecs, metadata and browser-preview transcoding. Codec availability depends on
the installed PyAV/FFmpeg build. Explicit unsupported choices fail visibly.
Animated containers carry frames rather than an audio track.

Caches live in `output/minimax_cache/<project_id>/`; a portable pack includes
reference/source media, not heavy generated takes. Lightweight imports cannot
prove a cache valid: actual dependency fingerprints must match. Unknown external
model loaders invalidate conservatively after restart; use the supplied loaders
for stable content provenance. Keep project IDs stable when reconnecting caches.

Conditioning Guide Output returns only the final shot's conditioning and empty
latent. It cannot represent an executable dependent multi-shot sequence.

## Optional dependencies and weights

Install only the providers you use in ComfyUI's environment:

| Feature | Dependency / local asset |
| --- | --- |
| Smart split | `scenedetect[opencv]` |
| Tracked face refine | `ultralytics`, detector under `models/ultralytics/bbox/` |
| Learned latent upscale | Compatible 24-channel 3D weights under `models/latent_upscale_models/` |
| Semantic Bridge | Compatible student weights under `models/semantic_bridge/` |
| Local text/vision Forge | `transformers>=4.57`, `accelerate`, complete model under `models/LLM/` |
| Local GGUF Forge | `llama-cpp-python`, GGUF and optional vision projection under `models/LLM/` |
| RTX effects | CUDA and NVIDIA VFX SDK/Python bindings matching the installed GPU runtime |

## Validation and license

The 2026-10-09 review passes **96 regression tests**, **14 real CPU PyTorch/PyAV
tests**, and an editor DOM integration scenario. GPU sampling, actual optional
model weights, RTX SDK execution and the remote ComfyUI deployment remain
unverified. Code consolidation does not establish visual quality or performance.

```sh
python -m unittest discover -s tests -v
python -m unittest discover -s validation -v
npm install --prefix .validation/ui jsdom@26 --no-save
node validation/test_editor.cjs
```

Run with real PyTorch available. The regression harness can substitute NumPy
when it is absent; the separate numerical/media suite requires real PyTorch.
The combined distribution is **GPL-3.0**. Selected upstream Apache/MIT notices
are preserved in [THIRD_PARTY_NOTICE.md](THIRD_PARTY_NOTICE.md) and vendor files.
