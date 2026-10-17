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
