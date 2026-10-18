# Current clip results — 1.7.14

Smart Preview offers Latest clip and Full video. Saved Take and its historical generation selector are removed. Existing preferences for that scope migrate to Latest clip.

Each clip has one current generation. A replacement publishes atomically after its files are saved; unsuccessful writes leave the previous current result usable. Successful replacement deletes superseded latent, audio, frame, source-media and refinement-stage files, plus derived previews referencing old generations. Current First Pass and Refine stages remain available. Browser buffers evict replaced generation revisions.

Checkpoint loads the current result. Its former take selector is removed; legacy API calls can identify the current revision but cannot load historical results. User-exported video files and project archives are outside this retention cleanup.

The idle migration `ProjectCacheManager.prune_history(include_orphans=True)` removes legacy history and orphaned managed artifacts only inside the selected project cache, preserving all files referenced by current results and staged drafts. It does not follow symlinks or arbitrary manifest file paths.
