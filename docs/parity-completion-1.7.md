# Parity completion — 1.7.0

This follow-up implements the three remaining functional gaps recorded after 1.6. No Master widgets/sockets or node types are added; the pack still registers 27 node types.

| Feature | Owner | Behavior |
|---|---|---|
| People-box editor | Reference Pack → Prompt Cast | Draw/move/resize, normalized coordinates, renumber/remove, up to 32 people. Media crop and person-box editing are separate modes. |
| Find People | Reference Pack, using a selected Forge provider | Vision detection returns editable proposals; explicit Use/Discard preserves reviewed boxes until acceptance. Shared cancellation and sampling guard apply. |
| Appearance cards | Forge → Cast Appearance Cards | One reviewed character/place/style/pose at a time. Reads only matching assigned images. Uses isolated-person crops; heavily overlapping people use full-frame position. Manual corrections remain authoritative. |
| Mode-aware writing | Forge backend | Separate opening/closing/paired-frame/reference/edit/still contracts. Reference-mode definitions use reviewed cards; keyframe modes receive cards as prose without incorrect REF2VA headers. |
| Transfer progress | Existing Project Import and portable project actions | Upload/download byte percentages; server extraction/restoration/packing progress. Job-scoped listeners, errors and cleanup. Upload completion is not labelled completed conversion. |
| Saved workflow recovery | Project Import | One recognized Director/Extender timeline, serialized reference/cast intent, explicit UNET loader aliases and saved DaSiWa prompt history. Multiple recognized timelines fail instead of silently selecting one. |
| Historical prompt review | Forge → Imported Prompt History | Prepare an archived prompt for review, inspect its reference tags, then use the existing reviewed Apply action. Old reference mappings are not silently declared verified. |

## Persistence and compatibility

People boxes are Reference Pack asset metadata and enter the existing reference pool. Cards and imported history persist with the timeline, named projects and portable archives. Current portable projects round-trip this data. Changes to cards/reference intent invalidate stale drafts through the existing context fingerprint. File-based vision follows EXIF orientation, with box coordinates defined against the original picture shown in the editor.

The provider transport is shared with normal Forge drafting: local, Ollama and compatible HTTP models, token/stream cancellation, configured model lifetime and explicit review. There is no second provider configuration in Master. Find People chooses an existing Forge node; session API keys stay in its transient password field.

Foreign recovery only uses data actually present in the input. Saved loader filenames, history and labels can be recovered; an omitted checkpoint filename, absent media file or opaque in-memory Python object cannot be manufactured. Procedural foreign graph patches are not executed during import. Unsupported fields, ambiguous timelines and missing installed assets remain explicit review errors/notices, rather than successful restoration claims. This is a data-availability boundary, not an unimplemented duplicate feature.

## Validation

Local checks cover box geometry and ordering, crop/overlap behavior, selected-image isolation, authoritative card compilation and stale-draft rejection, keyframe-mode prose, workflow history/model identities, ambiguous workflows, transfer progress, errors/cancellation/listener cleanup and portable round trips. The actual DOM tests exercise box draw/move/resize/renumber plus both review gates. The expanded two-panel layout fixture was inspected in a browser with a vector calibration picture; that fixture is not a generated-vision quality demonstration.

The older FEATURE_PARITY inventory now distinguishes implemented functionality from GPU certification and records the requested English-only UI as an intentional difference. Previous 1.6 server evidence and the interrupted sampling comparison remain in [server validation](parity-server-validation-2026-10-15.md); they are not retroactively presented as new 1.7 tests.

Local validation: **213 backend tests**, **36 real CPU tensor/media checks**, and **six JavaScript suites** pass. No new Master controls or node registrations were introduced.
