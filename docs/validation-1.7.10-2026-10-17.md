# Preview buffering and continuity audio 1.7.10

The player previously used metadata-only preload, and any failed polling request
removed the video source. It now buffers preview bytes independently of autoplay,
retains loaded footage during transient status failures, and checks again when
the browser returns to the foreground or regains connectivity. Authoritative
run/approval exclusions still remove ineligible footage.

Revision-addressed browser caches share downloads between players and take/scope
switches. Persistent storage is bounded to 32 entries / 1 GiB, session storage to
8 entries / 256 MiB; storage-denied browsers still use the session cache. Larger
media falls back to browser streaming. Once generation is idle, the full preview
is prepared and buffered in the background. A full MP4 is a separate media object
and requires its own initial transfer; it cannot reuse arbitrary byte ranges from
individual take MP4s. Browser eviction or cleared site data can require a re-download.

Preview encoding now publishes via an atomic rename, so interruption does not
leave a partial MP4 treated as cached success.

Master output, preview and cached Project Video export share continuity-audio
preparation. Where a successor has discarded audio context, its prefix crossfades
into the predecessor before the cut. This removes the unnecessary fade-to-zero
dip without shortening the audio or moving video cuts. Zero Join Fade disables
this processing. Without overlap audio, de-click fades remain; independent model
outputs cannot be guaranteed to have matching voices, ambience or music.
Preview and segment cache revisions invalidate the former join behavior.

Local validation: 236 backend tests; 24 real tensor/media/HTTP tests covering
continuity joins, sample counts, resampling, MP4 output, range requests, interrupted
encoding and existing take eligibility; all six existing JavaScript suites plus
the new browser-cache suite. DOM tests verify autoplay-off buffering, transient
failure retention, foreground recovery, revision reuse and disposal. Browser-cache
tests cover coalesced downloads, persistence, failure retry and bounded eviction.

Live deployment and browser verification results follow below.

## Live results

Deployed commit `94427abc2948a6a5d2f1186bba38d34c3250de3d`; the status endpoint
confirmed loaded version 1.7.10 and the unchanged 27 public node types. The queue
was empty before restart. The browser-tested player matched the deployed JS
SHA-256 `9ace1c33289d86d30c7509dfe5a3242f6a08ef3c4b04c0e1fe60ba9deebe8d03`.

Real browser verification used the deployed media endpoints and the production
player in an isolated test page, with the previously generated four-clip project:
Latest buffered all 10.125 seconds at readyState 4 while paused and autoplay off.
A simulated failed status response retained that video at readyState 4. Full
buffered 40.083333 seconds with one initial transfer and played successfully.
After page reload, Latest and Full both restored fully buffered with zero media
requests. Saved Take buffered once and switching away/back did not fetch it again.
No browser errors were recorded. This verifies outage/reload recovery, not every
possible browser suspension duration or storage-eviction policy.

Deployed Project Video job `5e20d1b2-7736-4128-aa50-654367a3bb56` exported the
four existing clips in 7.830 seconds. Forced repeat export job
`5e35c00d-43f7-4571-8c0d-12a5f1d61b08` executed in 0.139 seconds, reusing segments.
PyAV decoded all 962 output frames at 1280x736, nominal 24 fps, with a decodable
audio stream and finite samples. No diffusion was rerun for these output checks.

The temporary test tab and authenticated Node browser proxy were closed.
