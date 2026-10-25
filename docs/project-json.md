# Editable project exports

By default, **Export Project** downloads a small `.mmxproj.json` file. It contains
the timeline, prompt builder, reference catalog and workflow node settings and
connections. It contains no model weights, source files or generated tensors.

`timeline.clips` is the single editable clip list. The Master node inside
`workflow` deliberately has no second embedded timeline; import injects the edited
timeline into it. Cache reports, browser drafts, selection flags and old runtime
generation fields are omitted from the editable clips.

For AI editing, keep existing clip IDs. For new clips, omit `id` to have import
assign one, or use your own unique ID such as `new_scene_4`. IDs are local text
identifiers, not server-issued records. Duplicate or unsafe IDs are rejected.
Use decimal strings for seeds, especially large 64-bit values.

Example new clip to append to `timeline.clips`:

```json
{
  "name": "New scene",
  "type": "REF2VA",
  "duration": 10,
  "prompt": "Describe this scene here.",
  "seed": "12345",
  "seed_mode": "fixed",
  "ref_names": ["Sami Face", "Abdo Face"],
  "continuity_mode": "Motion Context (Chained)",
  "context_length": 22,
  "audio_context_length": 22,
  "validated": false
}
```

Use `ref_names` with the names in `reference_catalog`. Import resolves names against
the current pool, so matching assets can occupy different internal slots. Names
must be unique. Add an asset with the matching name before importing; a name
alone does not supply its image/video/audio. Legacy `ref_ids` remain supported. Optional `result_bindings`
identify existing saved takes for the original clips. New clips do not need an
entry there, and an uploaded binding cannot create a cached result.

Import choices:

- **overwrite**: replace the timeline in the current workflow. Keep its current
  models, LoRAs, attention nodes, sampler and other connected node settings.
- **append**: add clips to the current timeline with fresh IDs.
- **workflow**: restore the exported workflow, its node settings and connections,
  and the edited timeline.

Approved clips stay approved when settings change. Manually uncheck a clip to
generate another take; this also unchecks its dependent continuity chain, stopping
at an independent clip. Missing or replaced approved results are reported rather
than silently regenerated. JSON-only exports can reconnect to results that still
exist on the same server; they cannot reproduce missing files on a new server.

Two optional archive checkboxes are off by default:

- **Include source/reference media** packages the input images, videos and audio.
- **Include generated results** packages saved clip latents, frames and audio.
  These archives can be much larger than media-only archives. Restored results
  enter a fresh project so existing server results are not overwritten.

Model weights, LoRA weights and installed custom nodes are not bundled. Those
must exist on the target ComfyUI installation. **Cancel download** aborts an
active export transfer. Older version-5 JSON exports and old media archives remain
importable, but older exports may not contain a workflow to restore.
