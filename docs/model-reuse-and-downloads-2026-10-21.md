# Cross-run model reuse and preview downloads

Release **1.7.19**, validated 2026-10-21.

## Findings from the user's two production runs

The latest successful Next Clip runs in project `first_video` took 197.09 and
179.43 seconds. They are not equivalent workloads: clip 1 sampled 243 frames;
clip 2 sampled 277 frames with continuity. The windows from sampling announcement
to decoding were approximately 85.48 and 122.02 seconds, respectively. Clip 1
spent substantially longer decoding/saving. Similar totals alone cannot measure
weight transfer or demonstrate duplicate sampling.

There was nevertheless an avoidable unload in our code: `RunResources.clear()`
called native `unload_model_and_clones()` at every execution boundary. Temporary
sampling-wrapper cleanup called the same family-wide operation. Those calls could
discard native residency for the reusable H3 base and its clones.

Both existing download endpoints returned authenticated HTTP 200 MP4 attachments:
Latest Clip about 1.9 MB and Full Video about 3.8 MB at the tested 540p preview cap.
The browser action was a plain link without an authenticated fetch/download handler,
progress or error feedback. The server-side export worked in this check; that alone
did not establish that clicking the browser link would save it.

## Implementation

- One process-wide active sampling configuration handle shares native base weights.
  It is not a second GPU weight store. There is no list of retained old configurations.
- Identical base, adapter contents/strengths, model-affecting settings and sigma shifts
  reuse the active configuration across executions. Seed and prompt are not model
  configuration keys. Changes replace the active configuration.
- Adapter file tensors are reused on CPU with a 256 MiB/eight-file upper bound.
  Oversized adapters are not retained in an extra file cache; their required tensors
  can still be held by the active native patcher. Changed adapter files remove stale
  versions of that file from the CPU cache.
- Run completion, cancellation and decode boundaries release temporary references,
  reference-encode working tensors and temporary files without calling a family-wide
  H3 unload. Native ComfyUI manages residency and clone-parent transitions. Changing
  to a genuinely different checkpoint releases the old base through native cleanup.
- ComfyUI's existing Free Memory/Unload Models request clears our active handle and
  CPU adapter cache before continuing to the native handler. No new node or setting
  was introduced, and no third-party/core source was edited.
- Save preview captures the displayed scope/revision, fetches through ComfyUI's API
  authentication and triggers an MP4 download. It shows preparation/download status,
  prevents duplicate clicks and reports server/network failures. Changing the scope
  or receiving a new generation does not redirect an already-started download.

## Validation

- 150 relevant backend tests passed locally and on the deployed Linux host.
  Follow-up model-residency diagnostics also passed the focused resource tests.
- Preview download, playback, replacement, cache, durability, progressive transfer,
  separate-node, editor and guide JavaScript suites passed.
- Real browser Save clicks produced two files. PyAV independently read their video
  and audio streams: Full Video had 144 frames (6 seconds), Latest Clip 72 frames
  (3 seconds). A screenshot is retained locally at
  `.validation/save-preview1719-verified.png`. These are synthetic browser fixtures.
- Three real reduced GPU jobs used REF2VA, the existing SLA node, a real clip-local
  REF2V Turbo LoRA, 320 x 192, two steps and 56 frames. All completed successfully:

| Test | Base model ID | Configuration ID | Native H3 base count before sampling | Total time |
|---|---|---|---|---|
| Cold run, adapter strength 0.7, seed 101 | 140198216197632 | 140200150827232 | 0, before first load | 121.25 s |
| Seed-only reroll, seed 102 | 140198216197632 | 140200150827232 | 1 | 16.21 s |
| Strength changed to 0.8, seed 103 | 140198216197632 | 140200149393984 | 1 | 15.38 s |

The seed-only reroll logged configuration reuse and did not log a new native
`Requested to load MiniMaxH3`. Changing strength replaced the configuration while
retaining the same base object. Native manager inspection deduplicated H3 objects;
it did not find an additional H3 base. The latter two completed-run RSS samples were
47,003.7 and 47,010.4 MiB, not another checkpoint-sized allocation.

## Limits and interpretation

These are functional, reduced-size smoke tests. Cold versus warm timings also
include model initialization, provenance hashing and reference preparation, so
they are not a full-resolution speedup benchmark or a long-run leak test. Small
test sequences used SLA's dense fall-through path.

Keeping one configuration does not pin every H3 weight on the GPU. Native dynamic
VRAM management can still page/offload weights to accommodate the text encoder,
VAEs and sampling buffers. A `Requested to load` message can also identify a new
patcher/configuration rather than a new physical base; native staging messages alone
do not measure complete checkpoint rereads. The model/configuration IDs above are
runtime identities, not persistent cache keys.

Reload the browser page to activate the updated Save handler. Backend version
1.7.19 was verified after an idle-queue restart. Temporary test browser/server
helpers were closed after validation.
