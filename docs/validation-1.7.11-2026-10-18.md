# Master and preview repairs — 1.7.11

This release addresses the nine findings in `master-preview-review-2026-10-18.md` within existing nodes. It adds no nodes or Master controls and changes no third-party source.

- Normalize paired reference-video soundtrack keys at the native executor boundary.
- Centralize editor approval invalidation for generation-affecting edits, including dependent continuity clips. Runtime seed advancement preserves approval. External authored prompt/content changes also reject old approvals; unchanged authored groups retain them.
- Let the first chained clip consume an explicitly connected checkpoint without trimming a nonexistent timeline predecessor.
- Persist recovery color settings and final-media requirements. Latent recovery uses the accepted take's saved color settings. Missing seam-graded/face-refined final frames, or older takes without recovery provenance, require restoring final media or explicitly unapproving; they cannot silently become different accepted pixels.
- Keep Conditioning Only from starting a media freshness epoch. Explicitly reused staged drafts become reviewable in the new run without copying tensors.
- Associate historical first-pass metadata with its completed take. Older takes without this association report that stage unavailable instead of displaying another draft.
- Restore preview stage and saved-take selection when loading node configuration.
- Retry Saved Take playback failures with bounded backoff. After three automatic retries, show an explicit Refresh action.
- Evict failed media from memory and persistent browser caches and bypass HTTP cache on the next media fetch.

Local validation: 243 backend tests and 32 real CPU media/HTTP/memory tests passed; seven JavaScript suites passed, including new regressions for approval chains, historical stage restoration, bounded retries and persistent/HTTP cache recovery. Targeted Master tests cover paired soundtrack slots, checkpoints, conditioning freshness, draft reuse/history and immutable accepted-media recovery.

Live deployment and GPU test results are recorded below after execution. Local tests use controlled model stand-ins and do not establish GPU performance or CUDA stability.
