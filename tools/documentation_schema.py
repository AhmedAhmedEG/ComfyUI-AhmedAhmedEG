"""Read public node contracts in an isolated process without loading model weights."""
import json
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def collect():
    from tests.mock_torch import setup_mock_torch_if_needed
    setup_mock_torch_if_needed()
    folder = types.ModuleType("folder_paths")
    folder.models_dir = str(ROOT / ".validation/documentation-models")
    folder.get_filename_list = lambda name: ["(Installed files)"]
    folder.get_folder_paths = lambda name: []
    folder.add_model_folder_path = lambda *args: None
    folder.folder_names_and_paths = {}
    sys.modules["folder_paths"] = folder
    import comfy
    samplers = types.ModuleType("comfy.samplers")
    samplers.KSampler = types.SimpleNamespace(SAMPLERS=["euler", "res_multistep"], SCHEDULERS=["simple"])
    sys.modules["comfy.samplers"] = samplers
    comfy.samplers = samplers
    from nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
    dynamic = {"sampler", "scheduler", "latent_upscale_model", "model_name", "adapter_name"}
    result = {}
    for key, cls in NODE_CLASS_MAPPINGS.items():
        inputs = []
        for section, fields in cls.INPUT_TYPES().items():
            if section == "hidden": continue
            for name, spec in fields.items():
                kind, opts = spec[0], spec[1] if len(spec) > 1 else {}
                choices = kind if isinstance(kind, list) else []
                variable = name in dynamic or any(str(v).startswith(("(Installed", "Place ", "(Place ")) for v in choices)
                default = opts.get("default", choices[0] if choices and not variable else None)
                if variable and default is not None and str(default).startswith(("(Installed", "Place ", "(Place ")):
                    default = None
                inputs.append({"name": name, "type": "COMBO" if choices else kind,
                    "required": section == "required", "default": default,
                    "choices": [] if variable else choices, "dynamic": variable,
                    "description": opts.get("tooltip", ""),
                    "min": opts.get("min"), "max": opts.get("max"), "step": opts.get("step"),
                    "connection": opts.get("forceInput", False) or not choices and kind not in ("STRING", "INT", "FLOAT", "BOOLEAN")})
        labels = getattr(cls, "RETURN_NAMES", cls.RETURN_TYPES)
        result[key] = {"name": NODE_DISPLAY_NAME_MAPPINGS[key], "category": cls.CATEGORY.split("/", 1)[-1],
            "inputs": inputs, "outputs": [{"name": label, "type": kind} for label, kind in zip(labels, cls.RETURN_TYPES)],
            "source": str(Path(sys.modules[cls.__module__].__file__).relative_to(ROOT)).replace("\\", "/")}
    return result


if __name__ == "__main__":
    print(json.dumps(collect(), ensure_ascii=False))
