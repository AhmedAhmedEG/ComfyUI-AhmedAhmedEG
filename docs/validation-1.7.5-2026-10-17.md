# Release 1.7.5: four-clip workflow validation

The deployed process reported version 1.7.5 and 27 nodes. Code commits are `d8b267c` (progress recovery, pool-owned sizing and video labels) and `b5f8bc2` (refresh take availability when a completed event is missed). Both were pushed and installed. No third-party node source or allocator settings were modified.

## Actual generation

An isolated copy of the saved **MiniMax H3 Master Node** workflow generated all four REF2VA clips. Prompts, assets, clip order, ten-second requested clip durations, seeds and continuity were retained. Only the test copy changed:

- Generation mode: All clips; approvals cleared to require actual generation.
- Output: 320 × 192, 24 fps.
- Sampling: two steps, Euler/simple, existing CFG and shifts.
- Pool image/video preparation: Megapixels, 0.05 MP for this quick test.
- Separate project ID: `validation_user175_1792242526840`.

Job `79953ffa-bb90-44b0-acad-2c8f1d628344` completed successfully in 503.23 seconds, including cold preparation and loading. This was actual sampling, not approved-take replay. The four-clip Full Preview plan reports 4/4 completed clips and no missing clips.

The assembled MP4 was downloaded and decoded: 962 frames, 320 × 192, 24 fps, 40.083333 seconds, with finite nonzero 48 kHz audio. Frame-grid alignment and continuation assembly determine the exact duration. Two-step output is a functional test, not a quality benchmark.

## Live UI and routing checks

The authenticated browser opened the isolated workflow during generation. The timeline recovered the running clip after mounting mid-run. The marker moved from clip 1 to clips 2 and 3; clip 4 was also identified by the live status and progress state. The pulse CSS animation was active. After the run, the browser reported Idle and the endpoint reported active=false.

Recorded progress snapshots identify Preparing, Sampling and Decoding for each of the four clips, with the actual prompt ID. The websocket recorder received only the initial Preparing event; polling recovered subsequent state and drove the browser marker. This directly exercises the missing-event recovery path.

The deployed Reference Pack displayed Video + Audio, Video Only, Audio Only and Single Frame. Selecting Single Frame revealed the picked-frame control; selecting Video Only hid it again. Video + Audio was restored afterward. Resize displayed Megapixels and the test's 0.05 MP value.

The live Master contained no video-input resolution panel. The editor regression also checks its absence on video-based clips. Backend routing tests verify REF2VA and RV2V receive pool-prepared pixels without applying an obsolete per-clip budget. Real CPU tensor tests cover graph/file inputs and independent output dimensions. Served JavaScript matches the tested local source after normalizing line endings.

The live test exposed a related missed-event issue: take availability could stay stale after the next clip began. The deployed follow-up refreshes saved-result availability when the active clip changes and when polling detects the run has ended. Its editor regression passes.

## Other checks and cleanup

- 229 backend tests, 17 relevant real tensor/media tests and all six JavaScript suites passed. The editor suite passed again after the take-availability follow-up.
- The generic saved-workflow converter shifted serialized Master state because the saved graph contained a retired blank widget. The isolated test recovered the timeline by its content and used named fields; third-party conversion code was not changed.
- The validation copy is saved separately as `Validation 175/All four clips.json`, with visible step controls synchronized to two steps.
- The original saved workflow was fetched again and compared structurally: unchanged.
- Final queue: zero running, zero pending.
- The temporary localhost connection is closed. No task-owned proxy, generation monitor or preview-download Node process remains.

Local evidence is under `.validation/user175-*`, including the submitted graph, job/history, progress snapshots, preview plan, media check and assembled `user175-full.mp4`. These test artifacts and user prompts/assets are not included in this report's public source.
