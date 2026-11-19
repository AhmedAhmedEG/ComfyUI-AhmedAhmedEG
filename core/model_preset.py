"""Model preset selection shared by the Model Preset node and preflight checks."""

PRESETS = ("Base", "Lightning LoRA", "Fast H3")

# Exactly the values of the reference Fast H3 workflow (KSamplerSelect euler,
# BasicScheduler simple/8/1.0, BasicGuider = no CFG, MiniMaxH3SigmaShift 12/3).
# The distilled model is only valid with these; they are not user-editable.
FAST_H3_SAMPLING = {"steps": 8, "cfg": 1.0, "sampler": "euler", "scheduler": "simple",
                    "shift_video": 12.0, "shift_audio": 3.0}

MODEL_INPUT = {"Base": "base_model", "Lightning LoRA": "lightning_model", "Fast H3": "fast_model"}


def selected_inputs(preset, connected=()):
    """Input names the preset needs: (model, video VAE)."""
    if preset not in MODEL_INPUT:
        raise ValueError(f"Unknown model preset {preset!r}.")
    vae = "fast_video_vae" if preset == "Fast H3" and "fast_video_vae" in connected else "video_vae"
    return MODEL_INPUT[preset], vae


def preset_sampling(preset, base_steps, lightning_steps):
    if preset == "Fast H3":
        return {"preset": preset, **FAST_H3_SAMPLING}
    return {"preset": preset, "steps": int(base_steps if preset == "Base" else lightning_steps)}
