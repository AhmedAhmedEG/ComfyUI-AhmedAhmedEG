# Illustrated guide validation — 1.7.14

The guide was rebuilt against the current repository's node schemas on
2026-10-18. This validates documentation and its interface, not GPU output quality.

- 27 public node chapters cover all 269 declared input/settings names.
- 102 additional editor controls explain the timeline, continuity/look/LoRAs,
  project panel, reference editor, preview, Prompt Forge and export selectors.
- 11 screenshots were captured from the installed ComfyUI interface. A separate
  SVG is labelled as a wiring diagram, rather than a screenshot.
- Every node chapter uses the same eight sections. Option cards explain what a
  control does, when to use it, its effect and relevant limitations; defaults,
  ranges and enumerated choices come from the current schema.
- Former manuals redirect to current chapters, avoiding competing explanations.
- The builder checks package version, node coverage, input coverage and static
  choice explanations. A new node or field requires guide maintenance.

`python tools/build_user_guide.py` and `node validation/test_user_guide.cjs` passed.
The automated check covers generated local links, assets and anchors; current
navigation; exact-option search links; editor/workflow search; option filtering
and empty results; screenshot enlargement; menu/keyboard interactions and legacy
redirects. Search uses a bundled script rather than network requests.

Browser review checked the home page, Getting Started layout and diagram,
Refine option navigation/filtering, and full-size Reference Pack screenshot.
The home had no horizontal overflow at the inspected 1086-pixel viewport; its
visible image loaded. The closed lightbox intentionally has no image source.
Responsive CSS and menu behavior were checked, but no physical mobile device
was used.

No runtime node code or third-party code changed. No generation was submitted
and ComfyUI did not need a restart for these documentation changes.
