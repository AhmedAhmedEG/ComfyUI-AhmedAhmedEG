# Node placement, presentation and integration audit

Follow-up: the confirmed issues are addressed in [1.7.2 integration/layout fixes](node-layout-fixes-1.7.2.md). The findings below describe the audited 1.7.1 baseline.

Date: 16 October 2026 (Africa/Cairo). Deployed implementation: 1.7.1, revision `0c59a4d`. This audit found problems; it is not a UI or integration pass certificate.

## Evidence and scope

The deployed `/object_info` supplied 27 pack registrations with 27 distinct identifiers and display names. All are under one `ComfyUI-AhmedAhmedEG` category root, across seven subcategories. The actual ComfyUI search menu showed the pack and its categorized entries. There are no duplicate Master registrations within this pack. Other installed native H3/Extender categories are separate packs and are not duplicate registrations belonging to this project.

Live frontend inspection covered the existing Master, Reference Pack and Smart Preview, plus freshly added Forge, Pixel Upscale and Project Import nodes in an isolated unsaved workflow. No generation was submitted during the visual audit. The final Refine visual pass could not be completed after browser reconnection: acquisition of the browser's error page was blocked by its URL security policy. No workaround was attempted. Refine is source/schema-reviewed here, not newly visually certified.

The live frontend is 1.51.10 with DOM-based node rendering. An actual screenshot is saved at `audit-images/forge-placement-1.7.1.jpg`. This captures the deployed UI, not a proposed redesign. Native controls and custom panels share the dark palette, but Forge remains excessively tall and exposes redundant/raw controls.

24 expected direct socket pairs matched deployed types, including Reference Pack → Master, modifier nodes → Master, Timeline Builder/Project Import → Master, Forge → Review/Apply, local provider → Forge, and Master → preview/export/pixel processing. Saved evidence is `.validation/node-placement171.json` and `.validation/node-compatibility171.json`. Type compatibility alone did not establish semantic compatibility: the merge reproduction below failed.

## Confirmed findings

1. **Typed imported timelines lose metadata at the Master boundary.** `core/timeline_input.py:merge_authored_timeline` imports clips, references and shared prompt, but does not copy `cast_cards`, `imported_prompt_history` or `shared_ref_ids`. Reproduction with an empty local timeline and a valid imported timeline returned `None` for all three. Browser-side Apply Converted Timeline is a separate path; successful route/archive tests did not cover this socket handoff. Repair belongs in the canonical timeline merge, with explicit authoring ownership and regression coverage, not extra Master controls.

2. **Standalone Review/Apply cannot directly feed the typed Master timeline socket.** Its output is `STRING`; the Master input is `MMX_TIMELINE`. Inline Forge Apply works through its existing reviewed update path, and JSON can pass through Project Import, but the direct standalone graph path is awkward. Preserve the existing string output for workflow compatibility and provide a canonical typed path; do not create another competing timeline editor.

3. **Forge has redundant and irrelevant UI fields.** The deployed frontend shows both native `api_key` and the custom Session API Key. It also shows raw `shot_descriptions` JSON despite `hide()` marking that widget hidden, alongside the intended per-clip instruction controls. The local provider selection still shows remote endpoint/key controls. The raw timeline textarea and Master selector also represent two input ownership paths without sufficiently clear connected/manual behavior. Consolidate visible provider/auth inputs and make hidden state work in the DOM renderer; retain graph socket compatibility.

4. **Pixel Upscale presents ineffective controls in Bicubic mode.** Live default selection is Bicubic, but RTX quality, denoise and deblur remain visible; backend Bicubic ignores those values. Its display name ends in “and Refine”, although this node performs decoded pixel/RTX processing and does not run H3 diffusion refinement. Use conditional controls and an accurate title. Keep standalone pixel processing separate from the in-generation Refine configuration, while retaining their shared resize helper.

5. **Master's `video` output is misleadingly named.** It is correctly typed `VHS_VIDEOINFO` and returns metadata; it is not a native `VIDEO` object and cannot feed Reference Pack's `VIDEO,IMAGE` input or stock Save Video. Label it `video_info` while preserving the output index/type. Master images/audio remain usable for frame-based export; Project/Shot Video Export supplies actual native VIDEO.

6. **Combined reference roles need a more compact presentation and explanation.** Eight full-width checkbox rows make the selected-asset form much taller. First Frame, Last Frame and Keyframe are Forge writing intent, not generation endpoint assignment, but the panel does not explain that distinction next to them. Use a compact role group and a short visible explanation; actual endpoint/asset selection remains owned by clip type.

## Placement decisions

| Responsibility | Appropriate owner | Assessment |
|---|---|---|
| Clip execution, approvals, prompt and timeline editing | Master | Keep here; no further modifier/authoring panels needed. |
| Selected asset edits, people boxes, reference roles | Reference Pack | Correct owner; role layout needs refinement. |
| RefMod browsing and metadata | RefMod Library → Reference Pack | Correct separation. |
| Drafting, cards, history and reviewed application | Forge | Correct owner; native/custom controls and manual graph adapters need clearer boundaries. |
| SelfLift, diffusion Refine, face refinement, Semantic Bridge | Dedicated configuration nodes → Master | Appropriate optional modifiers. |
| Decoded pixel upscale and interpolation | Standalone output processors | Appropriate; Pixel node belongs more clearly under Output than the generation Enhancements group. |
| Cached project/shot export versus current frame-batch mux | Project Video Export versus Video Combine | Distinct inputs and purposes; no need to remove either. Names/help should make cache export versus frame encoding obvious. |
| Portable open/save versus upstream conversion | Project block versus Project Import | Distinct purposes; retain shared conversion/archive implementations. |
| Group packers and standalone Review/Apply | Advanced graph authoring | Keep identifiers, but distinguish these manual wiring tools from everyday integrated authoring in menu labels/categories. |

Current menu groups have 2 Start here, 6 Enhancements, 5 Output, 5 References and prompts, 2 Checkpoints, 5 Timeline authoring and 2 Advanced graph tools entries. This is substantially better than one flat menu. Remaining improvements are clearer output/manual-tool placement and consistent concise display names, not new node proliferation.

## Cleanup

Only isolated audit nodes were added; no source implementation was changed or server restarted during this audit. The temporary `visual_comfy_proxy.mjs` process was identified by its exact command line and stopped (PID 7196 for the resumed audit). This report and screenshots are local audit artifacts.
