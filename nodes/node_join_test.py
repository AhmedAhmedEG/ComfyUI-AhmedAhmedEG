"""Hidden output node used by the Master editor's "Test join" button.

ComfyUI only runs a prompt that ends in an output node. The editor queues just
the Master node and its inputs plus this sink on the Master's status output, so
a join test runs no save, preview or combine nodes and writes no media files.
"""

CATEGORY = "ComfyUI-AhmedAhmedEG"


class MiniMaxH3JoinTestSink:
    DEPRECATED = True  # internal: hidden from the node menu
    OUTPUT_NODE = True
    CATEGORY = CATEGORY
    RETURN_TYPES = ()
    FUNCTION = "finish"
    DESCRIPTION = "Internal: receives the Master node's status during a Test join run."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"status": ("STRING", {"forceInput": True})}}

    def finish(self, status):
        return {"ui": {"text": [str(status)]}}
