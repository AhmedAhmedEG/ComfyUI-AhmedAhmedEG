# Faster cache checks

Checkpoint and clip-LoRA SHA-256 digests are stored in
`user/minimax_director/file_fingerprints.json` on the ComfyUI server. The bounded
index contains file metadata and hashes only. It holds no weights, latents or
GPU allocations, and survives server restarts when the user directory persists.

An unchanged file reuses its digest after checking its resolved path, device,
inode, size and nanosecond modification/change times. A changed file is hashed
again. Files changing during a scan are retried once; unstable files fail rather
than publishing a mismatched identity. Missing, corrupted or unwritable indexes
fall back to normal hashing. As with other metadata caches, this relies on the
filesystem reporting file changes correctly.

Reference/latent tensor checks reuse bounded SHA states when tensor identity,
layout, dtype, device and PyTorch mutation version match. Only weak references
and small hash states are retained, so the cache does not keep tensor storage
alive. Normal in-place changes, including changes through views, invalidate reuse.
Inference tensors without mutation counters are checked in full. Changes made
outside PyTorch's version tracking (for example external NumPy writes) must not
be treated as tracked tensor updates.

The fingerprint byte representation is unchanged, so this optimization does not
invalidate existing reference encodings merely by changing the hash algorithm.
The float-based fingerprint path streams its bytes rather than allocating an
additional full-size bytes object. No third-party code or new UI setting is needed.

The first check of a new or changed checkpoint still reads that file fully. The
optimization saves repeated scans, not the actual reads needed to load weights,
decode source videos or restore cached latents. Code checks and content checks of
untracked tensors still run normally.
