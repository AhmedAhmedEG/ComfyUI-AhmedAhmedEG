# Choose a node

The [illustrated user guide](docs/index.html) is the complete reference for version
**1.7.16**. Start with [Your first clip](docs/getting-started.html), then use
[Practical workflows](docs/workflows.html) or the
[timeline and reference editor guide](docs/editor.html).

The starter uses four tools from this pack: **Master**, **Director Settings**,
**Reference Pack**, and **Smart Preview**. Standard ComfyUI loaders supply the two
model families, text encoder and two VAEs. The Master chooses a compatible model
family for each clip. Optional enhancement nodes connect only when needed.

Each feature has one owner: Director Settings owns sampling/output dimensions;
Reference Pack owns connected media preparation; Master owns clip authoring and
continuity; Smart Preview owns playback. Reference assets enter through graph
inputs. Only the references assigned to a clip condition that clip.

## Current node menu

These are the actual ComfyUI menu categories. The illustrated guide sidebar also
groups pages by task to make them easier to learn.

| Menu | Node and guide | Purpose |
| --- | --- | --- |
| Advanced graph tools | [MiniMax H3 Clip Model Pack](docs/nodes/model-override-pack.html) | Name alternative model branches for individual clips. |
| Advanced graph tools | [MiniMax H3 Review / Apply Prompt Draft (Graph)](docs/nodes/apply-prompt-draft.html) | Apply a reviewed prompt proposal to timeline data. |
| Advanced graph tools | [MiniMax H3 Tail From Latent](docs/nodes/tail-from-latent.html) | Decode the end of a sampled H3 latent into reference video, paired sound and a final frame. |
| Checkpoints | [MiniMax H3 Advance Staged Take](docs/nodes/advance-checkpoint.html) | Choose explicitly between two continuation checkpoint objects. |
| Checkpoints | [MiniMax H3 Load Take Checkpoint](docs/nodes/checkpoint.html) | Load the current completed clip’s latent, frames and sound. |
| Enhancements | [MiniMax H3 Cache](docs/nodes/cache.html) | Reuse sufficiently similar internal model residuals during sampling. |
| Enhancements | [MiniMax H3 Director FaceRefine](docs/nodes/director-face-refine.html) | Track and refine a face crop, then blend it back into the video. |
| Enhancements | [MiniMax H3 Director Refine](docs/nodes/director-refine.html) | Rework a generated clip, optionally enlarging it first. |
| Enhancements | [MiniMax H3 Director SelfLift](docs/nodes/director-self-lift.html) | Do early generation steps on a smaller canvas, lift the latent, then finish at target size. |
| Enhancements | [MiniMax H3 Director Semantic Bridge](docs/nodes/director-semantic-bridge.html) | Configure a compatible learned conditioning adapter. |
| Output | [MiniMax H3 Export Cached Project / Shots](docs/nodes/project-video.html) | Export current cached clips or stages as a complete video. |
| Output | [MiniMax H3 Frame Interpolation](docs/nodes/frame-interpolation.html) | Add in-between output frames and increase FPS while preserving duration. |
| Output | [MiniMax H3 Pixel / RTX Upscale](docs/nodes/pixel-upscale.html) | Resize decoded pictures using interpolation, a learned image model or optional RTX effects. |
| Output | [MiniMax H3 Playback / Watermark / Loop](docs/nodes/output-processing.html) | Adjust decoded playback, add a watermark or create a loop. |
| Output | [MiniMax H3 Smart Preview](docs/nodes/smart-preview.html) | Review the latest completed clip or the current full sequence in the browser. |
| Output | [MiniMax H3 Video Combine & Audio Muxer](docs/nodes/video-combine.html) | Encode supplied frames and audio into a video file. |
| References and prompts | [MiniMax H3 Local Prompt / Vision Model](docs/nodes/local-prompt-model.html) | Configure a local Transformers or GGUF prompt-writing model. |
| References and prompts | [MiniMax H3 Prompt Forge Draft](docs/nodes/prompt-forge.html) | Draft editable clip prompts using a configured language/vision model. |
| References and prompts | [MiniMax H3 RefMod Library](docs/nodes/ref-mod-library.html) | Choose supported H3 reference-model bundles and their metadata. |
| References and prompts | [MiniMax H3 Reference Pack (Pool)](docs/nodes/ref-pack.html) | Prepare connected reference assets once, then let each clip choose its subset. |
| Start here | [MiniMax H3 Director Settings](docs/nodes/director-settings.html) | Set the output canvas and initial sampling settings. |
| Start here | [MiniMax H3 Master Node](docs/nodes/master-node.html) | Build and generate a sequence of clips from one timeline. |
| Timeline authoring | [MiniMax H3 Director Group (Image to Video)](docs/nodes/director-group-image-to-video.html) | Describe a text/keyframe clip as graph data. |
| Timeline authoring | [MiniMax H3 Director Group (Reference to Video)](docs/nodes/director-group-reference-to-video.html) | Describe one reference-guided clip as graph data. |
| Timeline authoring | [MiniMax H3 Director Groups Combine](docs/nodes/director-groups-combine.html) | Combine several graph-authored clip groups in input order. |
| Timeline authoring | [MiniMax H3 Project Import](docs/nodes/project-import.html) | Review and convert supported project data into this pack’s timeline. |
| Timeline authoring | [MiniMax H3 Timeline Builder](docs/nodes/timeline-builder.html) | Convert graph clip groups into one typed Master timeline. |

## Older workflows

Use the current [starter workflow](workflows/MiniMax%20H3%20Start%20Here.json) when
replacing removed wrapper nodes. Former Master Director UI workflows migrate on
import; API prompts use `MiniMaxH3MasterNode` as their `class_type`.

| Removed wrapper | Replacement |
| --- | --- |
| Model Loader | Stock Load Diffusion Model |
| Encoder Loader | Stock Load CLIP (`minimax`) and two Load VAE nodes |
| Native Video Output | Stock Create Video |
| Sampling Settings | Director Settings |
| Prompt Pack Bridge | Standard STRING output to Master `prompt_text` |
| Reference Pack Bridge | Reference Pack; chain packs for additional inputs |
| Director Guide / Planner Conditioning | Master conditioning output for timeline conditioning, or native H3 conditioning nodes for manual graphs |

The [architecture chapter](docs/architecture.html) explains connection types,
reference limits and boundaries between configuration nodes. Historical manuals
redirect to the current chapters so there is one maintained explanation.
