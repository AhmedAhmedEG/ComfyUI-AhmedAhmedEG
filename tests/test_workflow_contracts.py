"""Check real workflow widget order, including frontend-only seed controls."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.mock_torch import setup_mock_torch_if_needed
setup_mock_torch_if_needed()
from nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

ROOT = Path(__file__).absolute().parent.parent


def widget_specs(node_class):
    for group in ("required", "optional"):
        for name, spec in node_class.INPUT_TYPES().get(group, {}).items():
            kind, options = spec[0], spec[1] if len(spec) > 1 else {}
            if options.get("forceInput"):
                continue
            if isinstance(kind, list) or kind in ("STRING", "INT", "FLOAT", "BOOLEAN"):
                yield name, kind
                if kind == "INT" and options.get("control_after_generate", name in ("seed", "noise_seed")):
                    yield "control_after_generate", ["fixed", "increment", "decrement", "randomize"]


class WorkflowContracts(unittest.TestCase):
    def test_examples_match_current_widgets_and_sockets(self):
        folder = SimpleNamespace(get_filename_list=lambda name: {
            "diffusion_models": ["SELECT_FL2VA_CHECKPOINT", "SELECT_REF2VA_CHECKPOINT"],
            "text_encoders": ["SELECT_MINIMAX_TEXT_ENCODER"],
            "vae": ["SELECT_VIDEO_VAE", "SELECT_AUDIO_VAE"],
        }.get(name, []))
        samplers = SimpleNamespace(KSampler=SimpleNamespace(SAMPLERS=["euler", "res_multistep"], SCHEDULERS=["simple"]))
        import comfy
        with patch.dict(sys.modules, {"folder_paths": folder, "comfy.samplers": samplers}), patch.object(comfy, "samplers", samplers):
            for path in (ROOT / "workflows").glob("*.json"):
                data = json.loads(path.read_text(encoding="utf-8"))
                by_id = {n["id"]: n for n in data["nodes"]}
                for node in data["nodes"]:
                    cls = NODE_CLASS_MAPPINGS[node["type"]]
                    specs = list(widget_specs(cls))
                    values = node["widgets_values"]
                    self.assertEqual(len(specs), len(values), node["type"])
                    named = node["widgets_values_named"]
                    for (name, kind), value in zip(specs, values):
                        self.assertEqual(named[name], value)
                        if isinstance(kind, list):
                            self.assertIn(value, kind, (node["type"], name))
                        elif kind == "BOOLEAN":
                            self.assertIsInstance(value, bool)
                        elif kind in ("INT", "FLOAT"):
                            self.assertIsInstance(value, (int, float))
                        else:
                            self.assertIsInstance(value, str)
                    inputs = {k: v[0] for group in ("required", "optional") for k, v in cls.INPUT_TYPES().get(group, {}).items()}
                    for socket in node["inputs"]:
                        self.assertEqual(socket["type"], inputs[socket["name"]])
                for _, origin, slot, target, target_slot, kind in data["links"]:
                    self.assertEqual(by_id[origin]["outputs"][slot]["type"], kind)
                    self.assertEqual(by_id[target]["inputs"][target_slot]["type"], kind)

    def test_public_names_are_unique(self):
        self.assertEqual(len(set(NODE_DISPLAY_NAME_MAPPINGS.values())), len(NODE_CLASS_MAPPINGS))
        self.assertNotIn("MiniMaxH3MasterDirector", NODE_CLASS_MAPPINGS)

    def test_starter_has_only_the_five_everyday_nodes(self):
        data = json.loads((ROOT / "workflows/MiniMax H3 Start Here.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["nodes"]), 5)
        self.assertEqual({n["type"] for n in data["nodes"]}, {
            "MiniMaxH3ModelLoader", "MiniMaxH3EncoderLoader", "MiniMaxH3DirectorSettings",
            "MiniMaxH3MasterNode", "MiniMaxH3VideoCombine"})
        for left in data["nodes"]:
            for right in data["nodes"]:
                if left["id"] >= right["id"]:
                    continue
                lx, ly = left["pos"]; lw, lh = left["size"]
                rx, ry = right["pos"]; rw, rh = right["size"]
                self.assertFalse(lx < rx + rw and lx + lw > rx and ly < ry + rh and ly + lh > ry,
                                 (left["type"], right["type"]))


if __name__ == "__main__":
    unittest.main()
