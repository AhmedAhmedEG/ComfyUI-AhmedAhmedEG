# Refresh recovery and unnecessary replay work

## Unsaved timeline drafts

The Master saves a browser draft of its timeline and prompt-builder settings,
including approval flags, with a 150 ms debounce. Pending writes flush when the
page is hidden or left. Drafts are scoped to project ID and Master node ID in the
same browser origin. A newer draft is restored when that same project/Master is
reopened; newer workflow state wins. Other projects and Master nodes are isolated.
The index is bounded to 16 drafts and normally about 2 MB of browser storage.

This protects Master authoring state without an explicit workflow save. It is
not a backup of the complete graph, external input nodes, or other browser/server
origins. Browser storage is best effort; clearing it removes these drafts. Named
server projects and workflow files remain the durable full-graph backup path.

## Reconcile actual results

Cache-status reads check files and the current generation ID without loading
tensors. Approving a clip binds the approval to that saved generation. Missing or
replaced results reject that approval and its dependent continuity chain. A stale
generation-bound approval submitted directly to the backend fails explicitly;
it cannot silently approve a replacement. Legacy approvals without generation IDs
remain compatible and acquire an ID when the editor confirms their saved result.

Missed completions restore the generated seed. The seed's next value is recovered
only if the editor still holds the submitted seed, preserving a user's newer edit.
Pending first-pass review is recovered separately from completed refinement.
First-pass approval is likewise tied to the reviewed draft's generation ID.
Finding a saved clip never approves it automatically. Authoring recovery and
status reads do not delete results or authorize preview-cache writes.

## Less replay I/O in Latest mode

When an approved clip is immediately followed by another approved clip, Latest
output no longer reloads the earlier clip's RGB frames, audio and latent merely
to overwrite its runtime context with the following clip. Files are checked by
metadata; the last required predecessor still loads normally for continuity.
Full output continues to assemble all clips. Incomplete caches follow the normal
recovery/error path. No sampling, quality, output dimensions or continuity lengths
are changed by this optimization.

The largest remaining measured costs are sampling and VideoVAE decode. Changing
their workload, kernels or tiling requires separate profiling and quality checks;
this update makes no speculative changes to those paths. Text conditioning is
still encoded on each generated clip; a provenance-aware conditioning cache is
a possible later optimization, not part of this update.
