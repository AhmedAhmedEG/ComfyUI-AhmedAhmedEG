# Selected upstream implementations

The consolidated Director uses selected algorithm modules, not upstream plugin
registrations or separate Directors. Local adaptations are described below.

* `core/vendor/aimixer/`: AIMixer/ComfyUI_MiniMaxH3_Director revision
  `a8f57b8e23c46ee28fdb96796510fa7b4f3b1fbb`, Apache-2.0 (license beside code).
  Includes Euler-state SelfLift, spatial conditioning transforms, latent upscale,
  phase-aware continuation utilities, and per-step spatial tiled sampling.
  Native output adapters additionally accept modern `NodeOutput.result`.
  Checkpoint paths, safe loading, bounded caches and failure handling were
  strengthened locally. Face tracking/injection/stitching from the same pinned
  source retain its MIT attribution to Carasibana's ComfyUI-H3-FaceRefine.

* `core/vendor/dasiwa/`: darksidewalker/ComfyUI-DaSiWa-Nodes revision
  `aedf3592e57650494f68b4c8fb7f45edc25ca933`. Tiled diffusion, memory/temporal
  planning and refinement orchestration are GPL-3.0, with the license beside
  code. Its learned latent architecture retains the MIT notices in the source.
  Local adapters add explicit target canvases, external sigma schedules,
  modern native node output unwrapping, and composition with existing wrappers.
  Also includes selected PyAV video/animation encoding and preview transcoding,
  and optional RTX VFX effect lifecycle/DLPack adapters. Upstream route
  registrations are omitted; this package registers its own guarded routes.
  Continuation refinement locally separates full-prefix guide repinning from
  the seam mask. Safe .pt/.pth loading supplements the safetensors loader.

The combined distribution is GPL-3.0. Original Apache/MIT notices are retained.
The schema, upload/project routes, reference edits, prompt review, locale adapter,
native loader provenance, and output adapters are local implementations.

The vendor package has no ComfyUI node mappings, routes, or frontend registration.
Only the phase-aware continuation helpers used by the Director remain; unused
global context patch implementations and unrelated upstream pack helpers were
removed. Model weights remain user supplied.

Selected Spike Guard, RTX pair interpolation and supporting frame-generation utilities additionally come from DaSiWa revision `bdb62d4c561bbed30351974844e0168ad471331a` (GPL-3.0). Native registrations are omitted. Local adapters add explicit FPS/audio duration ownership and experimental defaults.

The pure tiled planner and diffusion window adapter are updated from DaSiWa revision `04ecdec250e24097ea2b3e3e339d607d14cf694b` (GPL-3.0). Local defaults retain 35% workspace headroom; Refine owns the planning toggle/reserve and Spike Guard direction. The locally adapted orchestration driver is retained.

The local people-box, cast-reader and reviewed-card implementation follows the audited DaSiWa 13–14 October cast workflow concepts, with independent shared-provider integration. Its storage, review gates and UI remain owned by Reference Pack and Prompt Forge. Upstream plugin/node registrations are not loaded.
