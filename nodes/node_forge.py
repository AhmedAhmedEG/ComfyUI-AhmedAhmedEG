"""Graph integration for local and remote prompt draft providers."""
import json
try:
    from ..core.forge import draft_prompts, apply_draft
except ImportError:
    from core.forge import draft_prompts, apply_draft


class MiniMaxH3PromptForge:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"timeline": ("STRING", {"default": '{"clips":[]}', "multiline": True}),
            "instruction": ("STRING", {"multiline": True}), "shot_count": ("INT", {"default": 1, "min": 1, "max": 100}),
            "backend": (["local", "ollama", "compatible"],), "endpoint": ("STRING", {"default": "http://localhost:11434"}),
            "model_name": ("STRING", {"default": ""})},
            "optional": {"generator": ("MMX_LLM_PIPELINE",), "api_key": ("STRING", {"default": ""}), "images": ("IMAGE",)}}
    RETURN_TYPES = ("MMX_PROMPT_DRAFT", "STRING")
    RETURN_NAMES = ("draft", "review_json")
    FUNCTION = "draft"
    CATEGORY = "ComfyUI-AhmedAhmedEG"

    def draft(self, timeline, instruction, shot_count, backend, endpoint, model_name, generator=None, api_key="", images=None):
        encoded = []
        if images is not None:
            import base64, io
            from PIL import Image
            for pixels in images[:12]:
                image = Image.fromarray((pixels.cpu().clamp(0,1).numpy()*255).round().astype("uint8")); image.thumbnail((1024,1024))
                output = io.BytesIO(); image.save(output,format="PNG"); encoded.append(base64.b64encode(output.getvalue()).decode())
        draft = draft_prompts(json.loads(timeline), instruction, shot_count, backend, endpoint, model_name, api_key, generator, encoded)
        return (draft, json.dumps(draft, ensure_ascii=False, indent=2))


class MiniMaxH3ApplyPromptDraft:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"timeline": ("STRING", {"multiline": True}), "draft": ("MMX_PROMPT_DRAFT",),
            "apply": ("BOOLEAN", {"default": False}), "policy": (["replace", "append"],)}}
    RETURN_TYPES = ("STRING",)
    FUNCTION = "apply"
    CATEGORY = "ComfyUI-AhmedAhmedEG"

    def apply(self, timeline, draft, apply=False, policy="replace"):
        return (json.dumps(apply_draft(json.loads(timeline), draft, policy), ensure_ascii=False) if apply else timeline,)


class MiniMaxH3LocalPromptModel:
    @classmethod
    def INPUT_TYPES(cls):
        try:
            from ..core.local_llm import model_names
        except ImportError:
            from core.local_llm import model_names
        return {"required": {"model_name": (model_names(),), "backend": (["transformers","gguf"],),
            "vision": ("BOOLEAN", {"default":False}), "device": (["cpu","cuda"],),
            "projection": ("STRING", {"default":""}), "context_length": ("INT", {"default":8192,"min":512,"max":131072})}}
    RETURN_TYPES = ("MMX_LLM_PIPELINE",)
    FUNCTION = "load"
    CATEGORY = "ComfyUI-AhmedAhmedEG"

    def load(self, model_name, backend="transformers", vision=False, device="cpu", projection="", context_length=8192):
        try:
            from ..core.local_llm import local_provider
        except ImportError:
            from core.local_llm import local_provider
        return (local_provider(model_name,backend,vision,device,projection,context_length),)
