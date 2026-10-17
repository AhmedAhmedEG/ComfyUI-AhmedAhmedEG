# Saved results are independent of approval — 1.7.12

The preview previously excluded saved results if their run ID differed from the last Master invocation and the clip was unapproved. In `first_video`, all four clips had complete saved frames, audio and latents, but that filter excluded clips 3–4, producing a 20.25-second Full Video. This was an incorrect preview policy, not missing results or a browser buffering failure.

Full Video now uses the latest saved result of every timeline clip, regardless of approval, run ID or an invalidation marker. Approval continues to control whether Master regenerates a clip. Preview requests do not modify approvals or saved tensors.

During execution, the submitted generation schedule excludes only results actually queued/running for replacement. Each completed clip becomes available immediately in that same running job. Next Clip does not hide other unapproved clips that are not scheduled for regeneration. Conditioning Only leaves all saved results viewable. Saved Take remains independent of the live schedule.

Validation: 244 backend tests and 34 real CPU media/HTTP/memory tests passed. Four player suites passed: preview, fresh-browser durability, preview node and browser cache. New real-MP4 tests cover four saved unapproved clips across different run IDs, unchanged contents/revision when approval changes, and Full/Latest updates and MP4 encoding after each of four completions within one still-running job. Queue tests also cover Next Clip, Conditioning Only and submitted regeneration taking precedence over later checkbox changes.

Live deployment checks use the existing `first_video` saved results, with no generation or changes to its approvals, latents or frames. The deployed process reports version 1.7.12 and 27 public node types. Its authoritative Full Video plan includes all four clips, with no missing clips. The actual rebuilt MP4 served HTTP 206 and contains 962 frames at 24 fps: **40.083 seconds**, 1280×736, with 48 kHz audio. All original saved generation IDs and approvals were verified unchanged. No GPU sampling was dispatched for this fix.
