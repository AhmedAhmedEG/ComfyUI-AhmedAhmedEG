# Master execution status

The existing green rgthree progress bar shows the Master clip number, current
operation and time spent in that operation beside its original text. Native
percentages and live previews continue to work. No separate status strip, extra
node or setting is added. If rgthree's bar is absent, no replacement UI is created.

Updates cover project/settings, reference-cache checks, uncached reference VAE
encoding, model/asset fingerprints, prompt tokenization and text encoding, LoRA
configuration, H3 sampler initialization and sampling steps, refinement, video
and audio decoding, result saving, output assembly and temporary-buffer cleanup.
The strip clears on completion, interruption or execution error.

“Loading as needed” describes the operation's native loading boundary. Dynamic
VRAM loads weights on demand and may reuse existing weights. The strip does not
claim to measure individual weight transfers or byte-by-byte load percentages.
Time is elapsed time, not an ETA, and stage boundaries are not fake percentages.

Instrumentation delegates existing calls unchanged. It sends small text events
at boundaries, skips duplicate updates, and limits sampler status to four updates
per second. The browser updates elapsed time once a second while visible. There
are no additional hardware queries, GPU synchronizations, tensor scans, model
loads or background polling tasks for this feature. Third-party code is unchanged.
