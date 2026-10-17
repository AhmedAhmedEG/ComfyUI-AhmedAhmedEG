# Final phased memory cleanup 1.7.9

Extends the measured continuity-wrapper improvement to every ordinary sampling-to-decoding boundary, including the first independent clip. Native model residency is released while execution-scoped wrappers remain alive for reuse. Reviewed first-pass and per-refine-pass video caches also stage pixels before audio work. This uses ComfyUI's targeted unload API, not global model unloading or third-party file changes.

Validation before deployment: 236 backend tests, 19 real tensor/media tests, and all six JavaScript suites. Prior 1.7.7 Full raw-output and 1.7.8 Latest raw-output runs each successfully generated all four ten-second clips at 1280x736, two steps. The final-release runtime test and approved/export checks follow below.
