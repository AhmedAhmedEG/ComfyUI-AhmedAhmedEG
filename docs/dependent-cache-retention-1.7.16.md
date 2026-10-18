# Dependent cache invalidation — 1.7.16

Queuing or sampling a replacement preserves the old timeline preview. After a
clip's replacement is durably saved, its continuity-dependent successors are no
longer usable: their current results, latent/audio/frame files, source-media
copies, staged drafts, refinement files and derived previews are removed.
Independent/source clips stop this chain; their results and later chains remain.

The cache manifest publishes the replacement and removes dependent entries in
one transaction. Physical cleanup follows publication; locked managed files use
the existing retry list. A failed replacement preserves the old parent and all
dependent entries/files. Exported videos and project archives are outside this
cleanup.

The Master clears affected successor approvals before it considers reuse. Each
regenerated successor re-enters the preview after its own successful save.
Invalidated clip IDs also evict their old browser media across preview stages.
Both preview scopes continue to prebuffer automatically with autoplay off.

Validation: 142 backend/CPU tensor/media tests and five preview suites passed,
plus the documentation suite. New cases cover deleting dependent drafts and
refinement/source artifacts, retaining independent chains, failed publication
rollback, regenerating a formerly approved successor, and browser eviction of
dependent final/draft media. No live diffusion job was submitted for these tests.
