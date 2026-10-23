# Clip cache reports and text conditioning

Click **Cache** on a timeline clip to see what its latest run reused or prepared
fresh. Each row explains what that data is. Raw lookup counts and file/tensor
identity checks are collapsed under **Technical checks and lookup counts**. Reports
survive browser refresh through project result metadata. Model setup reuse means
the patch configuration was reused; it does not prove weights stayed in VRAM.
Only consulted caches appear. The audio reference lane stays visible when empty.

Text conditioning is reused from `text_conditioning/` inside the project cache.
Its key includes the actual encoder tokens (including reference data), encoder
provenance, patches, options and implementation sources. Seed, sampling and clip
length changes can reuse it when they leave those encoder inputs unchanged.
Continuity guides, empty audio/video latents and sampling are still rebuilt.
Scheduled hooks and unsupported custom data bypass reuse. Entries are CPU files,
bounded to 32 files and 256 MiB per project; no extra GPU model cache is created.

Reference encoding is now prepared only for references selected by generated
clips. Startup registers connected asset IDs and prunes disconnected cache owners
without hashing or encoding all pool media. Selected media still needs reliable
content checking; an arbitrary loader's unchanged node ID cannot prove its pixels
are unchanged. Persistent file hashes and mutation-aware tensor hashes remain in
use. Tensors without reliable mutation counters are still scanned for correctness.

Reference preparation records include actual media content, canvas, duration,
reference sizing, VAE identity and native H3 implementation. A matching record
skips the extra native preparation pass; the real conditioning call loads its
encoded latents on demand. Missing or corrupt latent files recover through native
encoding. Records are bounded to 128; the CPU working set remains 128 MiB.
Cache ownership now uses connected asset IDs, so old content-key ownership may
require one initial rebuild after this update. This does not remove saved clips.

Loading titles distinguish **Checking Cache**, **Loading References** and
**Encoding References**, followed by **Text Conditioning**, **Preparing MiniMax H3**,
**Sampling**, **Refining**, **Decoding Video/Audio**, **Saving Clip** and
**Assembling Video**. Timers describe the current stage, not a guaranteed duration.
