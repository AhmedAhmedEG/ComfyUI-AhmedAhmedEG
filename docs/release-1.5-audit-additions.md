# Additions from the consolidation audit

The original 1.4.22 parity review identified gaps. Releases 1.5.0 and 1.5.1 implemented the following additions. Available features are not automatically enabled in an existing workflow.

| Location | Addition and behavior |
| --- | --- |
| Separate **Timeline Builder** (new node) | Builds an ordered typed timeline from Image/Reference groups. Stable group IDs preserve Master seeds, continuity and approval. A connected builder owns clip authoring; competing Master edits are disabled. |
| **Reference Pack**, existing node | Dedicated asset editor: names, roles, descriptions, file upload/drop/paste, trim seconds and waveform handles, normalized crop and drag crop rectangle, exposure/contrast/saturation, Off/Target/Fit And Pad/Divisible Crop scaling. Video can supply video plus audio, video only, audio only or a picked frame. Uploaded videos can provide an additional still image. Graph video FPS is normalized to 24. Stable IDs and paired sound are preserved. File previews and Forge vision do not reconstruct arbitrary procedural graph transforms. |
| Separate **RefMod Library** (new node) | Installed RefMod catalog, selections, stable IDs, descriptions and strength 0–4. Connects to Reference Pack; Master only assigns references to clips. |
| **Prompt Forge**, existing node | Draft/review interface with explicit reviewed apply, append/replace, three drafts of history, creativity/detail 1–10, per-clip descriptions, optional file-backed vision and a session-only API-key field. Rejects stale context, incompatible fixed clip types and competing edits to a builder-owned timeline. Cancel aborts the browser request and ignores late responses; provider computation may continue. |
| **Master + Refine** | First-pass approval caches the initial AV latent and preview and stops for review. The existing timeline approval checkbox approves this pending stage. The next run reuses a matching first pass; successors wait for review. Effective conditioning, encoders, continuity, initial latent/masks and audio changes invalidate stage approval. |
| **Refine**, existing node | Skip FL2V enabled by default; pixel preparation through learned upscale, RTX VSR or bicubic, alongside latent upscale. Conditioning and masks follow the new dimensions. Saves each refine pass for inspection and export. |
| **Smart Preview**, existing node | Stage selection: Final, First Pass, Before Refine or a numbered Refine Pass, while retaining Latest Clip / Full Video. |
| **Master runtime** | Known H3 VAE/text offload before refine while protecting active diffusion; version-gated prefetch/cast/vbar cleanup between clips. No GPU speed or VRAM improvement has been measured. |
| **Refine**, experimental control | Optional Spike Guard for learned latent upscaling, disabled by default. A heuristic with real synthetic tensor checks, not a universal quality guarantee. |
| Separate **Frame Interpolation** (new node) | Linear or RTX output interpolation, multiplier 2–8, FPS/audio duration preserved, endpoint/final hold and cut handling. CPU threshold-based cut behavior and SDK cut detection differ. Actual RTX/GPU operation is not verified; missing SDK support raises an error. |
| **Project Video**, existing node | Explicit clip-ID selection; fileless cached existing footage; mixed-resolution aspect-preserving padding; Final/First Pass/Before Refine/Refine Pass/Original Source streams; original soundtrack retention even when final output is muted; clip-at-a-time disk-backed export. |
| Separate **Project Import** (new node) | Reviewed conversion of recognized current/DaSiWa/AIMixer/Tritant metadata from JSON/ZIP/EXT. Embedded media goes to namespaced server input; stable converted IDs, foreign approval reset and warnings for missing/unsupported data. Does not import compatible foreign latent caches or model bindings. |
| Node widgets and documentation | Mode-sensitive widget visibility, backward-compatible serialization and updated node/workflow documentation. 27 registered node types. |

The four new nodes are Timeline Builder, RefMod Library, Frame Interpolation and Project Import. The other items extend existing nodes. Optional model-weight/RTX features have not been validated with a full GPU quality comparison.

Follow-up Reference Pack fixes: VIDEO/IMAGE input compatibility with native FPS/audio extraction; one selected asset's controls at a time; graph-local preview source resolution through reroutes, loader-change refresh and independent per-asset edits.
