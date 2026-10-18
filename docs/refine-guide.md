# Refine in the Master pipeline

Connect the Refine node's `refine` output to the Master's `refine` input and enable it. Refine runs after initial generation (including SelfLift, when connected). It applies to processed clips; validated clips continue to reuse their current result.

| Mode | Processing |
| --- | --- |
| `refine` | Additional diffusion at the existing resolution. Target dimensions do not change this mode's canvas. |
| `upscale` | Enlarge once, then run diffusion refinement at the target resolution. Additional passes reuse that resolution. |
| `latent_upscale` | Enlargement/preparation without an additional diffusion pass. |

`steps` adds work after initial sampling. `denoise` controls how much the result can change. More passes add further refinement, time, and opportunity for visual drift. Refinement can change faces, clothing, hands, motion, or flicker; improved quality is not guaranteed.

For an initial comparison, try same-resolution `refine`, one pass, three steps, denoise 0.2, and `global` backend. This is a conservative experiment, not a measured optimum. Compare First Pass and Final Output in Smart Preview.

## Main controls

- **Backend:** `global` retains first-pass audio while refining video. `sampler` processes the joint audiovisual latent and can change sound too.
- **Canvas:** `manual` uses width/height; `follow` preserves the actual first-pass aspect ratio and derives a target from megapixels. Dimensions snap to H3's 32-pixel grid. These controls apply when enlarging.
- **Upscale method:** latent preparation can interpolate or use a learned H3 latent upscaler. Pixel preparation decodes, enlarges, and re-encodes; learned pixel enlargement requires an `upscale_model` connection.
- **Refine model:** optional compatible alternative model for refinement; otherwise the current model is used.
- **Sampler/scheduler/sigmas:** configure refinement's sampling schedule. Optional external sigmas override the generated schedule.
- **Seeds:** Legacy uses clip seed plus pass index; Inherit reuses clip seed; Offset starts at clip seed + 1; Independent uses the separate refine seed plus pass index. Seed After Generate advances only the independent refinement seed.
- **Tiling/chunking:** memory-management options for larger canvases. The memory planner is a heuristic, not a guaranteed peak-memory cap.
- **Skip FL2V:** enabled by default to protect first/last-frame endpoints.
- **Spike Guard:** experimental latent correction; off by default.

## Review before refinement

Enable Confirm First Pass to pause after initial generation. Review the clip, approve the first pass on its timeline card, then run again. If the first-pass fingerprint still matches, the Master reuses it and performs refinement without repeating initial sampling. Continuity successors do not consume an unreviewed first pass.

First Pass, Before Refine, and Pass N are processing stages of the current clip result, not a history of previous generations. Replacing a clip removes superseded generation artifacts while retaining the current result's comparison stages.
