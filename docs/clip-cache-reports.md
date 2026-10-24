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

## Unchanged clips

An unapproved clip with a complete saved result is reused when its exact effective
generation inputs still match. Approval additionally preserves a chosen take
across input edits. An unchanged Next Clip run finishes without moving on to the
next unapproved clip; All Clips checks each clip. Actual replacements invalidate
dependent successors. Cache hits leave them intact. Changing the seed requests a
new variation; random/increment/decrement seed modes retain their existing behavior.
New identity fields and implementation changes can require an initial rebuild of
older results whose full input compatibility cannot be established safely.

The lazy-loader also checks a saved early input signature before requesting H3.
It covers authored settings, effective reference content, installed generation
code, checkpoint/LoRA files and supported upstream model wiring, plus continuity
predecessor generations. Standard UNET loaders, Turbo LoRA, Boolean model switches
and H3 SLA Attention are supported. Unknown modifiers, RefMod bundles, file-source
edits, face refinement, encoder hooks, dynamic seed modes,
missing files and old results without this signature use the full check. These
fallbacks may load H3. Text encoder and VAE inputs remain ordinary upstream inputs;
the early check does not require diffusion-model construction or sampling.

## Smart Preview outputs for RIFE

Smart Preview exposes **images**, **audio**, and **fps**. Its existing scope,
resolution and stage selectors also select these outputs for the next queued run.
Raw frames are assembled only when images or audio are wired to another node;
ordinary playback remains lightweight. Generated source FPS is 24.

For the installed **RIFE Frame Interpolation** node, connect Smart Preview images
to images and fps to source_fps. Set target_fps to **48** for 2x interpolation.
Connect the interpolated images to a video saver, set its FPS to the same **48**,
and connect Smart Preview audio to the saver. Raising export FPS without adding
frames speeds up playback instead of making motion smoother. RIFE generates the
extra frames; it does not alter H3's sampling FPS.

Loading titles distinguish **Checking Cache**, **Loading References** and
**Encoding References**, followed by **Text Conditioning**, **Preparing MiniMax H3**,
**Sampling**, **Refining**, **Decoding Video/Audio**, **Saving Clip** and
**Assembling Video**. Timers describe the current stage, not a guaranteed duration.
