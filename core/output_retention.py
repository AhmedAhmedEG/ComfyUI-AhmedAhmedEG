"""Bound decoded result retention without changing disk-backed project takes."""
class LatestClipBuffer(list):
    def append(self, value):
        self.clear()
        super().append(value)


def output_buffers(policy):
    if policy=='full':return [],[]
    if policy=='latest':return LatestClipBuffer(),LatestClipBuffer()
    raise ValueError('Decoded output must be full or latest.')
