# Clip cache reports and text conditioning

Click **Cache** on a timeline clip to see the lookups from its latest run: reused,
built/read, or bypassed. Shared run preparation is listed separately. Reports
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
