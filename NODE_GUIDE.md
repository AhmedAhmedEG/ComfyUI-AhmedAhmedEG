For the full reference, open the [documentation index](docs/index.html).
[Getting Started](docs/getting-started.html) explains the basic workflow; the
index links to a dedicated page for each of the 23 public nodes.

# Which nodes should I use?

The package has **23 public node types**, each with a single registered name.
The main editor is **MiniMax H3 Master Node**. Internal algorithms such as
conditioning construction, tile planning, tracking, cache serialization and
encoding adapters are Python modules, not nodes you must connect.

## Start here

Only **Master Node** and **Director Settings** come from this pack in the basic
workflow. Find them under **ComfyUI-AhmedAhmedEG → Start here**.

Use ComfyUI's stock nodes around them:

| Stock node | Connection |
| --- | --- |
| Load Diffusion Model ×2 | FL2VA → `fl2va_model`; REF2VA → `ref2va_model` |
| Load CLIP, type `minimax` | `clip` |
| Load VAE ×2 | Video VAE → `video_vae`; audio VAE → `audio_vae` |

The starter connects Master `project_state` to **Smart Preview**. Latest clip / Full video and autoplay live in that separate player. Reference Pack is the only authoring source for references, with optional names. The starter also includes both H3 SLA Attention patches and the Boolean switch for REF2VA Turbo LoRA and automatic 25/8-step selection. Settings has one Generation mode: Next shot / All shots / Conditioning only. Raw / Structured is per shot.

## Optional feature tools — fifteen types

You add these when you want the corresponding feature. They are user-facing,
not internal dependencies required to make the Master work.

| Menu | Node | Purpose |
| --- | --- | --- |
| Enhancements | Director SelfLift | Configure low/high-resolution generation |
| Enhancements | Director Refine | Configure a second refine/upscale pass and tiling |
| Enhancements | Director FaceRefine | Configure tracked face enhancement |
| Enhancements | Director Semantic Bridge | Apply a compatible prompt-conditioning adapter |
| Enhancements | Cache | Enable optional model acceleration; distinct from saved project takes |
| Enhancements | Pixel / RTX Upscale and Refine | Upscale decoded frames; optional RTX effects |
| Output | Video Combine & Audio Muxer | Advanced codecs, audio encoding, metadata, trim and first/last-frame export; use stock Create/Save Video for ordinary saves |
| Output | Project / Shot Video Export | Export saved shots or assemble the project from disk |
| Output | Playback / Watermark / Loop | Change playback, add branding or make a loop |
| References and prompts | Reference Pack (Pool) | Supply references from other graph nodes; direct uploads already work inside the Master |
| References and prompts | Prompt Forge Draft | Generate a draft through a graph workflow; also available inside the Master editor |
| References and prompts | Review / Apply Prompt Draft | Explicitly apply a reviewed graph draft |
| References and prompts | Local Prompt / Vision Model | Load an optional local model for graph-based drafting |
| Checkpoints | Load Take Checkpoint | Select a saved take as continuation input |
| Checkpoints | Advance Staged Take | Explicitly switch from a current take to a staged take |

## Advanced graph tools — five types

These support manual/custom workflows. You can ignore this category when using
the normal Master editor:

- **Director Group (Image to Video)**, **Director Group (Reference to Video)**
  and **Director Groups Combine:** build shot groups outside the timeline.
- Connect external text directly to Master **prompt_text**, one shot prompt per line.
  Use Reference Pack (Pool) for graph-supplied images/video/audio.
- **Tail From Latent:** manually extract continuation frames/audio from a latent.
- **Shot Model Pack:** supply named models for per-shot overrides.

The normal workflow uses standard ComfyUI loaders and video output. Uploads, crop/trim, source
editing, shared references, LoRAs, RefMods and the editor's Prompt Forge do not
require you to add a separate node for each action.

## Removed duplicates in 1.0.5

| Removed node | Replacement |
| --- | --- |
| Model Loader | Stock Load Diffusion Model |
| Encoder Loader | Stock Load CLIP (`minimax`) + two Load VAE nodes |
| Native Video Output | Stock Create Video |
| Sampling Settings | Director Settings |
| Prompt Pack Bridge | Connect standard STRING output directly to Master `prompt_text` |
| Reference Pack Bridge | Reference Pack (Pool); chain packs for additional inputs |
| Director Guide / Planner Conditioning | Master Conditioning Guide Output for timeline conditioning; native H3 conditioning nodes for manual graphs |

Load the new starter instead of the previous wrapper-based template. No alternate
or deprecated registrations are kept in the node library.
