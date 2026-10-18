# Preview replacement — 1.7.15

Starting or queuing a regeneration no longer hides a clip's saved result.
Approval controls Master reuse, while preview reads each clip's current published
result. An All clips run can therefore display newly completed replacements
alongside the still-current results for clips that have not finished yet.
This intentionally replaces the former run-freshness filter.

The existing atomic server save remains the replacement boundary. Failed saves
preserve the previous result; successful saves replace its files and remove
superseded derived previews. No historical take list is added.

The player keeps its current video loaded while the new revision buffers. Latest
and Full both prebuffer during generation, independent of autoplay. Browser
storage remains bounded and best effort; oversized videos use browser streaming.
Revision bookkeeping is serialized so simultaneous scope/player completions do
not lose cache-eviction entries. Polling backs up completion events.

Validation on 2026-10-19: 38 backend/CPU tensor/media/retention checks passed,
including real MP4 encoding and HTTP range delivery. Five player/cache suites
passed, covering a delayed replacement transfer, queue-start retention, both-scope
prebuffering with autoplay off, persistent cache replacement, concurrent revision
bookkeeping, reload durability and retry cleanup. The documentation suite passed.
These checks do not run diffusion or compare generated quality.
