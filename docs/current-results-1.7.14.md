# Current clip results — 1.7.14

Smart Preview offers Latest clip and Full video. Saved Take and its historical generation selector are removed. Existing preferences for that scope migrate to Latest clip.

Each clip has one current generation. A replacement publishes atomically after its files are saved; unsuccessful writes leave the previous current result usable. Successful replacement deletes superseded latent, audio, frame, source-media and refinement-stage files, plus derived previews referencing old generations. Current First Pass and Refine stages remain available. Browser buffers evict replaced generation revisions.

Checkpoint loads the current result. Its former take selector is removed; legacy API calls can identify the current revision but cannot load historical results. User-exported video files and project archives are outside this retention cleanup.

The idle migration `ProjectCacheManager.prune_history(include_orphans=True)` removes legacy history and orphaned managed artifacts only inside the selected project cache, preserving all files referenced by current results and staged drafts. It does not follow symlinks or arbitrary manifest file paths.

Validation: 248 backend tests, 67 real tensor/media/retention checks, the editor and four preview browser suites passed. The documentation browser suite checked all 27 node pages. A deployed 320×192, two-step test reused three approved clips and regenerated only clip 4. Its current latent/audio/frame files replaced the previous revision; Latest encoded 56 frames and Full encoded all four clips in 197 frames. No production-resolution quality comparison was performed.

Deployment migration removed 84 superseded managed artifacts and reclaimed approximately 51.3 GiB across 22 projects, verifying that 60 current clip entries and all their existing referenced files remained intact. Exported videos and archives were outside the cleanup scope.
