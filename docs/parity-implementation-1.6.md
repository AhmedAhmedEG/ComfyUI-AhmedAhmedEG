# Parity additions prepared for 1.6.0

This follow-up implements the actionable gaps from the October 14 source audit.
It adds no public Master widgets or sockets and no new node types. The existing
27-node ownership structure remains intact. Runtime validation is recorded below; local tests alone are not comparative GPU certification.

| Feature | Single authoring owner | Shared execution path |
|---|---|---|
| Refine seed policy, uint64 seed and after-generation advancement | Refine | `core/refine_controls.py`; every global/sampler/tiled refinement round uses the same resolver. |
| Follow First Pass aspect with MP / Manual sizing | Refine | Existing `core/resolution.py` planner, applied to actual latent dimensions at runtime. |
| 9999-round refinement range | Refine | Runtime and Project Video pass selector agree on the supported range. |
| Fit/Fill/Stretch and floating-channel Lanczos | Pixel Upscale; Refine only selects its preparation policy | `core/pixel_resize.py` is used by standalone and integrated decoded upscaling. |
| Cast groups, multiple people, positions, retention, writer Include/Ignore | Reference Pack, collapsed Prompt Cast | `core/forge_cast.py` validates metadata and compiles native clip-local labels. Writer Ignore does not change model reference selection. |
| Per-clip instruction text boxes, chronological predecessor context and stale-take rejection | Prompt Forge | `core/forge.py` / `core/forge_context.py`; graph calls and HTTP authoring use the same draft/apply helpers. |
| Prompt model lifetime | Local Prompt Model | Lazy graph-held handles load only when drafting; default unload runs on success and error. Keep Loaded is explicit. Ollama receives keep_alive=0. |
| Sampling guard | Forge HTTP route | Refuses a new browser draft while ComfyUI's execution queue is running. |
| More faithful authoring conversion | Project Import | Current extra authoring fields retained; recognized foreign continuity/context, LoRA enable/strength, sources and guide timing mapped to canonical runtime fields. |
| Auto-download verified H3 upscale weights; reserve planning and Spike Guard direction | Refine | Pinned size/SHA-256, streaming atomic install; shared tiled planner with 35% default workspace reserve. |
| Compatible archive cache and explicit binding restoration | Project Import | Raw Tritant H3 descriptors validated before writes, one segment at a time; installed checkpoint aliases, converted Config and RefMod outputs use existing contracts. |
| Cancellation and stable prompt tags | Forge | Cooperative local token stop, remote stream close, stable reference-ID mappings remap native labels at execution. |
| Large-batch decoded retention | Settings, Decoded Output | Latest mode keeps one decoded result buffer; generated takes still use normal durable cache. Smart Preview / Project Video own full-sequence preview/export. |

## Compatibility decisions

- Full decoded output remains the default. Latest deliberately returns only the
  latest clip from Master's direct IMAGE/AUDIO ports; consumers needing the whole
  sequence use Project Video or keep Full. The status output identifies the policy.
- Latest mode fails on generated-take cache errors instead of claiming earlier
  outputs were retained durably. The current clip, model, graph references and
  continuity latents still need working memory; this is not a total RAM/VRAM cap.
- Refine's Legacy policy retains previous `clip_seed + pass_index` behavior.
  Inherit holds the clip seed; Offset starts at clip seed + 1; Independent uses a
  decimal uint64 seed plus the round index. Values wrap within uint64. No precision
  is lost through a JavaScript numeric seed field.
- Manual canvas and integrated pixel Stretch preserve old refine defaults.
  Follow explicitly preserves aspect with an MP budget. Standalone Pixel Upscale
  now honors its previously ignored Fit/Fill selection.
- First-pass identity excludes refine-only controls. Changing the independent
  refinement seed can reuse an approved matching first pass without new initial
  sampling. A fully approved final take still follows the user's reuse policy.
- Tritant audio context `0` means Follow Video. Conversion turns it into the
  explicit video span, because `0` means Off in our runtime. This translation is
  reported rather than silently changing audio conditioning.
- Authoring-only imports clear approval. Explicitly restored compatible native H3 takes preserve source approval and decode using connected VAEs without initial diffusion. Current project Save/Open keeps its existing role.
- Appending a prompt draft carries its applicable reference bindings with a new
  clip ID. A continuation replacement preserves earlier clips and rejects a
  predecessor take that changed after drafting.
- Updated bundled workflows include new ordinary widgets in schema order. New
  mode-sensitive controls hide when irrelevant. Manuals and generated guides
  document where each feature lives.

## Explicit remaining boundaries

Recognized foreign fields are translated, not silently treated as executable graph state. Tritant raw H3 caches can be restored explicitly; arbitrary cache serializers, unnamed in-memory checkpoint objects and historical foreign Forge state are not reconstructed. AIMixer authoring packs do not contain equivalent native latent caches. Missing asset/model names remain explicit report entries. Embedded Tritant Clip 0 becomes a locked Existing Video predecessor; its CSS saturation/contrast/brightness grading order is retained when restored takes are decoded. Preserve original projects.

Automatic download is opt-in for one pinned compatible latent upscaler. RTX SDKs and arbitrary checkpoints still require installation. The source-shaped tiled planner now follows the October 14 DaSiWa implementation, retaining our target canvas, external schedule, continuity and native-output adapters. Its budget is a conservative estimate, not a guarantee of fixed peak memory. Latest decoded output additionally offloads continuation state to CPU without truncating H3 temporal phases.

Cancellation stops local generation at token boundaries and closes remote streaming connections. A provider may continue computing after disconnection. Model lifetime cleanup runs after generation exits, including cancellation; actively executing weights are not freed from a competing thread.

Current source heads checked: DaSiWa `04ecdec250e24097ea2b3e3e339d607d14cf694b`, AIMixer `4c6245e518dd8a494f3afc4f3cccd53f22d82d10`, Tritant `5183ad4e1449cf1eaa835bc5fdff08cab7cc57d9`. These are later than the original consolidation pins. AIMixer adds import/export progress; Tritant's intervening commit is README-only. DaSiWa additionally introduces a richer draggable people-box/cast-reading editor; this implementation retains reviewed cast assignments/positions rather than claiming that editor exists here. Unrelated general utility-node additions are outside MiniMax scope.

Real H3, LoRA, learned-upscaler, bridge, face detector and RTX quality/performance
comparisons still require suitable installed models and controlled GPU runs.
No claim of benchmarked superiority, fixed peak VRAM, or universal visual
equivalence follows from these additions.

## Validation

Regression coverage includes Master -> Refine policy routing, unchanged staged
first-pass reuse when refining with a new seed, latest-only output with both takes
on disk, actual per-round seed/callback behavior, foreign reference remapping,
disabled LoRA preservation, cast native numbering, continuation Apply boundaries,
local provider cleanup on errors, and real pixel padding/cropping/Lanczos checks.

The authoring tests exercise per-clip instruction persistence, collapsed cast
metadata, Refine mode visibility, builder ownership, exports and reviewed imports.
The Master schema remains unchanged. GPU/provider operation beyond controlled
fixtures is not included in local test results.

Verified locally: **204 backend regression tests**, **36 real CPU tensor/media checks**, and **five JavaScript editor/preview/documentation suites** passed. Windows sandboxing blocked a loopback HTTP test on the first attempt; the test completed successfully when run with loopback access. Those are local tests. Subsequent real-server results, including the interrupted sampling comparison and successful VAE/cache replay checks, are recorded in [server validation](parity-server-validation-2026-10-15.md).
