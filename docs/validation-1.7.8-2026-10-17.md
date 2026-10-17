# Final memory lifecycle follow-up 1.7.8

Builds on the successful 1.7.7 full-output stress run. Newly created Settings nodes and bundled starter workflows default to latest raw IMAGE output; All Clips still generates and persists every clip, and full project preview/export remains available. Existing explicit Full settings are preserved. Latest output returns the private mapped final take view without writing another full raw output file.

Continuity remask wrappers are registered in our execution scope and released via native targeted cleanup before decoding, including error paths. Latent-only approved-take repairs stage RGB before audio decoding, and alternate export frame streams use mappings. No third-party source or global loaded-model lists are modified. Dependencies declare psutil in both requirements and package metadata. Runtime validation and final measurements follow below.
