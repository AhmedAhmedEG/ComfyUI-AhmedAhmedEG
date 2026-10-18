# ComfyUI MiniMax H3 Master Director

Version **1.7.16** consolidates the MiniMax/video production features of
[DaSiWa](https://github.com/darksidewalker/ComfyUI-DaSiWa-Nodes),
[AIMixer](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director), and
[Tritant](https://github.com/tritant/ComfyUI_MiniMax_H3_Extender) into one Director.
[FEATURE_PARITY.md](FEATURE_PARITY.md) records the pinned sources, required union,
and subsystem choices. These choices follow code/API review; they are not GPU
quality or speed benchmarks. See [REVIEW.md](REVIEW.md) for validation evidence.

The separate **Smart Preview** node plays the **latest completed clip** by default.
Switch to **Full video** to review the completed sequence. Each scope has its own
cached H.264/AAC preview file. Playback buffers with autoplay off, retains loaded
video during temporary status failures, and reuses browser-cached revisions.
Both Latest clip and Full video prebuffer as results finish, including during an active
run. Saved results remain viewable until each successful replacement is published;
a queued regeneration does not clear the player. Once a predecessor is replaced,
its continuity-dependent successors lose their old cached artifacts and approvals.
The dependency chain stops at an independent/source clip; rebuilt successors return
to the preview as they finish.
The browser keeps up to 32 previews / 1 GiB in persistent storage when available
and up to 8 previews / 256 MiB in session memory. Larger media uses browser streaming.
Continuity audio joins blend the successor's discarded audio prefix into its
predecessor before the cut, preserving timeline duration. Independent clips use
de-click fades; sound content continuity still depends on generation audio context.

Each feature has one configuration owner. Settings controls canvas and sampling.
Reference Pack owns media preparation; RefMod Library owns character adapter
descriptions and strengths; Prompt Forge owns draft creation and review.
The Master owns local clip prompts, continuity, ordering, approval and projects.
Add Clip can insert an existing video from the connected Reference Pack. Continuity
uses the immediately preceding timeline clip. External authoring connects through
Timeline Builder and disables competing authoring fields in the Master.

Refine can pause for first-pass approval, reuse that saved latent, and save every
refinement pass for Smart Preview or Project Video export. Pixel/RTX upscale can
run before refinement. Experimental Spike Guard is off by default. Frame
Interpolation and reviewed upstream Project Import are separate optional nodes.

## Install and start

There is one public **MiniMax H3 Master Node** name. The package has 27 distinct
user-selectable tools, organized by purpose; internal algorithms are not separate
nodes. Under `ComfyUI-AhmedAhmedEG`, Master and Director Settings are in
`Start here`, Reference Pack is in `References and prompts`, and Smart Preview
is in `Output`.
[NODE_GUIDE.md](NODE_GUIDE.md) explains the everyday and optional tools.
[Open the illustrated user guide](docs/index.html), or begin with
[Your first clip](docs/getting-started.html). The guide covers all 27 public nodes,
269 declared inputs/settings, and the controls inside the timeline, reference editor,
Prompt Forge and export panels. Each node follows the same structure: purpose,
wiring, first use, options, practical examples, outputs and troubleshooting.
Use [Practical workflows](docs/workflows.html) for continuity, input megapixels,
LoRAs, refinement and export; [Timeline & reference editor](docs/editor.html) explains
the in-node controls. Full-text search, option filters and enlarged screenshots work
offline; keep the docs folder together. The starter download needs the adjacent
workflows folder. Rebuild with `python tools/build_user_guide.py`; authored content
lives in the guide JSON files under `docs/`, and the builder checks option coverage
against the current node schemas. Former manual links redirect to current chapters.
Saved UI workflows using the former Master Director type migrate on import.
API prompts should use `MiniMaxH3MasterNode` as their `class_type`.

Copy `MiniMaxH3Director` into `ComfyUI/custom_nodes/`, install `requirements.txt`
with ComfyUI's Python, and restart ComfyUI. The installed ComfyUI must provide
native MiniMax H3 ImageToVideo, ReferenceToVideo, AddGuide, SigmaShift and current
`comfy_api.latest` VIDEO APIs.

Load `workflows/MiniMax H3 Start Here.json`. It uses standard **Load Diffusion
Model** (FL2VA + REF2VA), **Load CLIP** (type `minimax`), two **Load VAE** nodes,
and a separate **Smart Preview** node connected to `project_state`. It previews **Latest clip** by default; **Full video** is an explicit switch in the player. H3 SLA Attention (plaguekind-nodes) patches both model families, and a stock Boolean/model switch enables the supplied REF2VA Turbo LoRA. The same toggle automatically selects 8 steps for Turbo or 25 for the base model; edit the two integer nodes to change those values. Reference media enter through **Reference Pack (Pool)**; give connected items optional names. The Master, Settings, Reference Pack and Smart Preview are this pack’s four nodes in the starter. The saved filenames match the current server’s MiniMax H3 models. Check the five selections, edit
a clip and select connected Reference Pack assets in the Master. Both diffusion models are lazy:
only the family required by the timeline’s shot modes is requested.

`MiniMax H3 Consolidated.json` adds optional advanced export nodes, muted by
default. The Master tracks standard loader provenance internally for saved-take
reuse. Unknown third-party loader/modifier paths retain conservative live-session
cache identity. Use the fresh starter after updating from 1.0.4; removed wrapper
nodes are intentionally no longer registered. See NODE_GUIDE.md for replacements.

After `git pull`, **restart the ComfyUI process**, then reload the browser.
Pulling files does not reload Python node registrations in a running server.
`/minimax_director/status` reports the loaded version and installation path;
version 1.7.16 reports 27 types and only `MiniMaxH3MasterNode` as the Master.
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
- **References:** connected Reference Pack assets with per-clip type/count limits, media
  playback and trim, real waveform handles, draggable crop preview, exposure/
  contrast/saturation, scaling/divisible crop, roles/descriptions, frame picking,
  embedded video V/A/V+A switching, and RefMod bundles/library descriptions.
- **Prompt Forge:** reviewed editable multi-shot drafts from local Transformers
  or GGUF, Ollama, or a compatible API, with optional vision. Drafts preserve
  context and require explicit apply. Changed source context invalidates a draft.
- **Continuity:** independent, endpoint handoff, native motion guides in every
  video mode, or phase-aware latent carry with redraw masks. Prefix/video/audio
  trim is shared by previews and cached exports. Importing an existing video
  creates locked Clip 0. Current clip results can be loaded as checkpoints and advanced
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
- **Projects/output:** atomic current results per shot, restart provenance, autosave/recover,
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
Disk assembly reads one mapped cached shot at a time and reuses unchanged
encoded segments. Master assembles IMAGE output in bounded frame windows;
large outputs use temporary disk-backed storage instead of one giant RAM
allocation. Latest output avoids assembling the complete sequence. Models,
current-clip decoding and continuity tails still require working RAM/VRAM.
Temporal refinement stages its complete output/noise in host RAM and enforces
a memory budget.

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

Version 1.7.2 passes **221 regression tests**, **36 real CPU tensor/media checks**,
and six editor/preview/documentation/transfer interaction suites. Tests include actual
FFmpeg assembly, staged and intermediate previews, media edits, immutable approved
takes and typed external authoring. GPU sampling comparisons, optional real model
weights and RTX SDK execution remain unverified. Project conversion supports
reviewed authoring metadata and embedded media, not foreign latent-cache formats.
See [the revalidation](docs/feature-parity-revalidation-2026-10-14.md) and [the additions and compatibility boundaries](docs/parity-implementation-1.6.md).

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

Named projects: expand Project, enter Project Name and use Save Project. Open Project lists projects stored on this server and reopens their full workflow. Names and cache IDs persist inside ordinary saved workflows. Project metadata lives in output/minimax_projects; large generated tensors stay in output/minimax_cache.
