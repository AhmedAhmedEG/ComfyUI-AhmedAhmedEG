# Which nodes should I use?

The package has **30 public node types**, each with a single registered name.
The main editor is **MiniMax H3 Master Node**. Internal algorithms such as
conditioning construction, tile planning, tracking, cache serialization and
encoding adapters are Python modules, not nodes you must connect.

## Start here — five types

Find these under **MiniMax H3 → Start here**. The consolidated example connects
them for you; select your model files and edit the timeline.

| Node | What you use it for |
| --- | --- |
| Master Node | Timeline, shots, prompts, uploads, reference editing, selection and generation |
| Model Loader | Load your FL2VA and/or REF2VA diffusion checkpoint; use two instances for both |
| Encoder Loader | Load the text encoder, video VAE and audio VAE together |
| Director Settings | Resolution, sampling, batch execution and continuity settings |
| Video Combine & Audio Muxer | Preview and save the generated video with audio |

All display names start with **MiniMax H3**.

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
| Output | Native Video Output | Connect decoded results to ComfyUI nodes accepting VIDEO |
| Output | Project / Shot Video Export | Export saved shots or assemble the project from disk |
| Output | Playback / Watermark / Loop | Change playback, add branding or make a loop |
| References and prompts | Reference Pack (Pool) | Supply references from other graph nodes; direct uploads already work inside the Master |
| References and prompts | Prompt Forge Draft | Generate a draft through a graph workflow; also available inside the Master editor |
| References and prompts | Review / Apply Prompt Draft | Explicitly apply a reviewed graph draft |
| References and prompts | Local Prompt / Vision Model | Load an optional local model for graph-based drafting |
| Checkpoints | Load Take Checkpoint | Select a saved take as continuation input |
| Checkpoints | Advance Staged Take | Explicitly switch from a current take to a staged take |

## Advanced graph tools — ten types

These support manual/custom workflows. You can ignore this category when using
the normal Master editor:

- **Director Guide** and **Director Planner Conditioning:** manually build
  conditioning/latents from a guide dictionary.
- **Sampling Settings:** supply or override a sampling configuration separately.
- **Director Group (Image to Video)**, **Director Group (Reference to Video)**
  and **Director Groups Combine:** build shot groups outside the timeline.
- **Reference Pack Bridge** and **Prompt Pack Bridge:** adapt external images
  and prompt lists into the Master.
- **Tail From Latent:** manually extract continuation frames/audio from a latent.
- **Shot Model Pack:** supply named models for per-shot overrides.

The normal workflow needs the five starter types. Uploads, crop/trim, source
editing, shared references, LoRAs, RefMods and the editor's Prompt Forge do not
require you to add a separate node for each action.
