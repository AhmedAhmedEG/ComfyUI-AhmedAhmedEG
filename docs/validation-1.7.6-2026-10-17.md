# Release 1.7.6: approval and current-run preview

Smart Preview polls while visible, recovers missed shot events, and excludes old unapproved future takes while a project is running or queued. Approved clips remain reusable and visible. Submitted queue approvals take precedence over a checkbox changed after enqueue. Freshly completed results remain available for review before approval; older takes remain accessible explicitly through Saved Take.

Unchecking final approval also unchecks continuity-dependent successors, stopping at an independent, source, or locked clip. This changes timeline flags only. Latents and saved media are not deleted. Regeneration replaces the active generation pointer while retaining saved-take history. Clip LoRA edits use the same dependency invalidation.

Validation: 231 backend tests, 15 focused real CPU media/progress checks, and all six JavaScript suites passed. The media check encodes only a fresh one-second clip despite an old future take being present. Dependency tests verify independent-boundary behavior. Persistence tests verify old/new latent files survive unapproval and regeneration. No third-party code was changed.

## Separate unexpected process termination

Read-only inspection of retained Docker logs and comfyui.prev.log confirms the previous process was killed on 2026-10-17 at 15:39:12 UTC (18:39 Cairo). Clips 1 and 2 completed; clip 3 completed 20 sampling steps and entered VAE decoding before the entrypoint reported `Killed`. Docker then restarted the container at 15:39:13 UTC. This is distinct from the authorized Manager deployment restart at 13:06 UTC.

No Python/CUDA traceback appears at this termination. Current Docker State reports OOMKilled=false and ExitCode=0; current cgroup v1 counters show no OOM kills, but these readings after restart do not establish why the previous process received a kill. Memory pressure remains unconfirmed. This release does not claim to fix that termination. Startup completed with PyTorch loaded; Manager's conflicting prestartup check and optional ONNX/OpenGL/legacy-API warnings are separate observations.
