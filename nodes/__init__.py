"""Node package registration for MiniMax H3 Master Director."""

from .node_director import MiniMaxH3MasterDirector
from .node_selflift import MiniMaxH3DirectorSelfLift
from .node_refine import MiniMaxH3DirectorRefine
from .node_face_refine import MiniMaxH3DirectorFaceRefine
from .node_bridges import MiniMaxH3ReferenceBridge, MiniMaxH3PromptBridge
from .node_tail_extract import MiniMaxH3TailFromLatent

NODE_CLASS_MAPPINGS = {
    "MiniMaxH3MasterDirector": MiniMaxH3MasterDirector,
    "MiniMaxH3DirectorSelfLift": MiniMaxH3DirectorSelfLift,
    "MiniMaxH3DirectorRefine": MiniMaxH3DirectorRefine,
    "MiniMaxH3DirectorFaceRefine": MiniMaxH3DirectorFaceRefine,
    "MiniMaxH3ReferenceBridge": MiniMaxH3ReferenceBridge,
    "MiniMaxH3ReferencePackBridge": MiniMaxH3ReferenceBridge,
    "MiniMaxH3PromptBridge": MiniMaxH3PromptBridge,
    "MiniMaxH3PromptPackBridge": MiniMaxH3PromptBridge,
    "MiniMaxH3TailFromLatent": MiniMaxH3TailFromLatent,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MiniMaxH3MasterDirector": "MiniMax H3 Master Director",
    "MiniMaxH3DirectorSelfLift": "MiniMax H3 Director SelfLift",
    "MiniMaxH3DirectorRefine": "MiniMax H3 Director Refine",
    "MiniMaxH3DirectorFaceRefine": "MiniMax H3 Director FaceRefine",
    "MiniMaxH3ReferenceBridge": "MiniMax H3 Reference Pack Bridge",
    "MiniMaxH3ReferencePackBridge": "MiniMax H3 Reference Pack Bridge",
    "MiniMaxH3PromptBridge": "MiniMax H3 Prompt Pack Bridge",
    "MiniMaxH3PromptPackBridge": "MiniMax H3 Prompt Pack Bridge",
    "MiniMaxH3TailFromLatent": "MiniMax H3 Tail From Latent",
}
