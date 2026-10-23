# Retained models in Server monitor

Expand **Retained models** in the floating Server monitor. The list refreshes
every two seconds with the hardware meters and pauses when minimized or hidden.
It covers all GPUs, independently of the selected GPU meter.

Each row shows the native model class, target device, loading mode, cached model
size and reported bytes on that device. Dynamic VRAM additionally exposes tracked
host weight buffers and the pinned subset. Shared base models on the same device
are counted once. Process resident RAM and swap appear above the list.

These are native bookkeeping counters. They do not scan tensors, load models,
pin memory or clear caches. Unknown measurements display a dash. Standard loading
does not expose the Dynamic VRAM host counters. Model size is read only if ComfyUI
has already calculated it.

Host buffers cover tracked weights, not every CPU allocation or physical RAM
residency. Pinned bytes are a subset of host buffers. Process RAM, host buffers,
device bytes and Windows shared GPU RAM overlap: do not add them together. Shared
GPU RAM cannot be attributed to individual models using these counters. An empty
native loaded-model registry does not prove other execution caches hold no models.

The backend must load the updated pack before this section can report live data.
Existing servers display unavailable until that happens. No extra node or Master
setting is added.
