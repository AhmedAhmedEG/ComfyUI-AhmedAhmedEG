# Reference cache and progressive preview validation

Release: **1.7.18**, 2026-10-21.

## Changes

- Master prepares connected image, video and audio references through native H3
  preparation and persists missing VAE encodes under `reference_latents/` in the
  project. Files use RefMod's CPU safetensors convention: `latent` plus the
  `refmod_meta` header. Native audio layout is preserved when loading the cache.
- Cache identities include prepared tensor contents, encode arguments, native H3
  source identity and VAE provenance. Unknown modified VAEs conservatively use
  live-session identities. A bounded 128 MiB CPU working set holds reusable tensors;
  it does not retain them on the GPU. Disconnected sources lose their derived files.
- Preparing the pool does not add unselected references to actual conditioning.
  Preparation uses a presentation stub; real prompt/text encoding still receives
  only the selected references through the native conditioning call.
- Decode boundaries release temporary model wrappers but leave owned shifted
  models to native ComfyUI residency management until execution cleanup. This
  removes our forced unload of every owned sampler patcher at every decode.
- Smart Preview can play before a network transfer completes. Supported browsers
  compose the same per-clip H.264 fragments for Latest Clip and Full Video.
  A joined AAC soundtrack preserves the existing join fade/gain processing.
  Download and unsupported-browser playback retain the ordinary MP4 path.
- Browser buffering shares transfers and cached revisions. Superseded transfers
  cannot repopulate an invalidated cache entry after finishing late.
- Continuity prefix and visible PCM now resample together before splitting.
  Separate sinc-resampler boundaries previously created a large artificial jump
  in the mixed-sample-rate seam regression. This fixes a join artifact, not poor
  sound generated within a clip.

## Validation

- **145 backend tests passed on the Linux ComfyUI host**, including reference
  disk reuse, exact tensor equality, RefMod loading, audio layout, invalidation,
  corruption recovery, bounded CPU retention, model lifetime, audio joins,
  fragment encoding and duration, progress, and result/dependency retention.
- Preview, cache, durability, replacement, progressive-transfer, separate-preview,
  editor and guide JavaScript suites passed. The guide contains 27 node chapters,
  269 source fields and 11 existing live screenshots plus a wiring diagram.
- Real browser: deliberately held a video transfer after its first fragment.
  Playback opened before completion. After releasing it, two clips played on one
  six-second timeline. Latest/Full switching reused video transfers, with three-
  and six-second scopes respectively. This exposed and fixed an append-window
  transition error before deployment. Browser test screenshots are local under
  `.validation/preview1717-progressive.png` and `preview1717-cached-scopes.png`.
- Two isolated GPU runs used the existing REF2VA/SLA graph, two clips, 320 × 192,
  two sampling steps, existing prompts and continuity. The first succeeded with
  **6 reference misses / 8 hits**, preparing four images and a video's picture and
  soundtrack even though only two images were selected for clip conditioning.
- The second run disconnected the unused video and changed the first clip seed.
  It succeeded with **0 reference misses / 12 hits**. The reference index retained
  four image entries. Both clips emitted preparing/sampling/decoding/completed
  events. The deployed preview endpoint returned both current clip revisions;
  their video-only fragments and joined audio fragment decoded successfully.
- Loaded version and deployment location were verified from the live status API.
  No third-party custom node or ComfyUI core file was modified.

## Limits

The reduced GPU runs are functional smoke tests, not quality or full-resolution
speed comparisons. Cold first-run time was 182.45 seconds; the repeat was 55.12
seconds, but it had warm model state and no unused video preparation, so those
numbers are not a valid optimization speedup estimate. The small test sequence
fell below SLA's sparsity threshold and used its dense fall-through path.

Native model staging still uses substantial host RAM: the smoke run's recorded
high-water RSS was about 46,764 MiB with roughly 1.6 GiB swap. These changes do
not establish that full-resolution memory pressure has been eliminated. Browser
storage remains bounded and best effort; unsupported MediaSource codecs use the
regular streaming fallback. The combined soundtrack may need a small audio-only
transfer when the scope or timeline changes; cached video is reused.

For normal Smart Preview use, `decoded_output=latest` avoids assembling a full raw
frame/audio output batch. It does not limit generation to one clip or remove other
saved clips. Use `full` when downstream nodes on the Master's frame/audio sockets
need the entire sequence.
