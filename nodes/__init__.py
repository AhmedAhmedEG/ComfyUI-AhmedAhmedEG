"""Node package registration for MiniMax H3 Master Director."""

from .node_director import (
    MiniMaxH3MasterDirector,
    MiniMaxH3DirectorGuide,
    MiniMaxH3DirectorPlannerConditioning,
)
from .node_selflift import MiniMaxH3DirectorSelfLift
from .node_refine import MiniMaxH3DirectorRefine
from .node_face_refine import MiniMaxH3DirectorFaceRefine
from .node_semantic_bridge import MiniMaxH3DirectorSemanticBridge
from .node_cache import MiniMaxH3Cache
from .node_groups import (
    MiniMaxH3DirectorGroupImageToVideo,
    MiniMaxH3DirectorGroupReferenceToVideo,
    MiniMaxH3DirectorGroupsCombine,
)
from .node_settings import (
    MiniMaxH3DirectorSettings,
    MiniMaxH3SamplingSettings,
)
from .node_bridges import MiniMaxH3ReferenceBridge, MiniMaxH3PromptBridge
from .node_tail_extract import MiniMaxH3TailFromLatent
from .node_video_combine import MiniMaxH3VideoCombine
from .node_ref_pack import MiniMaxH3RefPack

# Primary alias requested by user
MiniMaxH3MasterNode = MiniMaxH3MasterDirector

NODE_CLASS_MAPPINGS = {
    # Flagship Master Node (named MiniMax H3 Master Node)
    "MiniMaxH3MasterNode": MiniMaxH3MasterNode,
    "MiniMaxH3MasterDirector": MiniMaxH3MasterDirector,
    "MiniMaxH3DirectorGuide": MiniMaxH3DirectorGuide,
    "MiniMaxH3DirectorPlannerConditioning": MiniMaxH3DirectorPlannerConditioning,

    # Dedicated Settings & Configuration
    "MiniMaxH3DirectorSettings": MiniMaxH3DirectorSettings,
    "MiniMaxH3SamplingSettings": MiniMaxH3SamplingSettings,

    # Core modules (SelfLift, Refine, FaceRefine, Semantic Bridge, Cache)
    "MiniMaxH3DirectorSelfLift": MiniMaxH3DirectorSelfLift,
    "MiniMaxH3DirectorRefine": MiniMaxH3DirectorRefine,
    "MiniMaxH3DirectorFaceRefine": MiniMaxH3DirectorFaceRefine,
    "MiniMaxH3DirectorSemanticBridge": MiniMaxH3DirectorSemanticBridge,
    "MiniMaxH3Cache": MiniMaxH3Cache,

    # Groups
    "MiniMaxH3DirectorGroupImageToVideo": MiniMaxH3DirectorGroupImageToVideo,
    "MiniMaxH3DirectorGroupReferenceToVideo": MiniMaxH3DirectorGroupReferenceToVideo,
    "MiniMaxH3DirectorGroupsCombine": MiniMaxH3DirectorGroupsCombine,

    # Bridges & Utilities
    "MiniMaxH3RefPack": MiniMaxH3RefPack,
    "MiniMaxH3ReferenceBridge": MiniMaxH3ReferenceBridge,
    "MiniMaxH3PromptBridge": MiniMaxH3PromptBridge,
    "MiniMaxH3TailFromLatent": MiniMaxH3TailFromLatent,
    "MiniMaxH3VideoCombine": MiniMaxH3VideoCombine,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MiniMaxH3MasterNode": "MiniMax H3 Master Node",
    "MiniMaxH3MasterDirector": "MiniMax H3 Master Node",
    "MiniMaxH3DirectorGuide": "MiniMax H3 Director Guide",
    "MiniMaxH3DirectorPlannerConditioning": "MiniMax H3 Director Planner Conditioning",

    "MiniMaxH3DirectorSettings": "MiniMax H3 Director Settings",
    "MiniMaxH3SamplingSettings": "MiniMax H3 Sampling Settings",

    "MiniMaxH3DirectorSelfLift": "MiniMax H3 Director SelfLift",
    "MiniMaxH3DirectorRefine": "MiniMax H3 Director Refine",
    "MiniMaxH3DirectorFaceRefine": "MiniMax H3 Director FaceRefine",
    "MiniMaxH3DirectorSemanticBridge": "MiniMax H3 Director Semantic Bridge",
    "MiniMaxH3Cache": "MiniMax H3 Cache",

    "MiniMaxH3DirectorGroupImageToVideo": "MiniMax H3 Director Group (Image to Video)",
    "MiniMaxH3DirectorGroupReferenceToVideo": "MiniMax H3 Director Group (Reference to Video)",
    "MiniMaxH3DirectorGroupsCombine": "MiniMax H3 Director Groups Combine",

    "MiniMaxH3RefPack": "MiniMax H3 Reference Pack (Pool)",
    "MiniMaxH3ReferenceBridge": "MiniMax H3 Reference Pack Bridge",
    "MiniMaxH3PromptBridge": "MiniMax H3 Prompt Pack Bridge",
    "MiniMaxH3TailFromLatent": "MiniMax H3 Tail From Latent",
    "MiniMaxH3VideoCombine": "MiniMax H3 Video Combine & Audio Muxer",
}
