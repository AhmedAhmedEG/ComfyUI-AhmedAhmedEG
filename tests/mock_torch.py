"""Lightweight mock torch implementation for running unit tests in environments without PyTorch installed."""

import sys
from unittest.mock import MagicMock
import numpy as np


class MockTensor(np.ndarray):
    """Numpy-backed Mock Tensor supporting core PyTorch tensor operations."""
    def __new__(cls, input_array):
        obj = np.asarray(input_array).view(cls)
        return obj

    @property
    def device(self):
        return "cpu"

    def numel(self):
        return int(super().size)

    def item(self):
        return super().item()

    def tolist(self):
        return super().tolist()

    def clone(self):
        return MockTensor(self.copy())

    def cpu(self):
        return self

    def cuda(self):
        return self

    def to(self, *args, **kwargs):
        return self

    def float(self):
        return MockTensor(self.astype(np.float32))

    def long(self):
        return MockTensor(self.astype(np.int64))

    def view(self, *shape):
        if len(shape) == 1 and isinstance(shape[0], (tuple, list)):
            shape = shape[0]
        return MockTensor(self.reshape(*shape))

    def reshape(self, *shape):
        if len(shape) == 1 and isinstance(shape[0], (tuple, list)):
            shape = shape[0]
        return MockTensor(super().reshape(*shape))

    def permute(self, *dims):
        return MockTensor(np.transpose(self, dims))

    def movedim(self, source, destination):
        return MockTensor(np.moveaxis(self, source, destination))

    def repeat(self, *repeats):
        return MockTensor(np.tile(np.asarray(self), repeats))

    def unsqueeze(self, dim):
        return MockTensor(np.expand_dims(self, dim))

    def squeeze(self, dim=None, axis=None):
        target_dim = dim if dim is not None else axis
        arr = np.asarray(self)
        return MockTensor(np.squeeze(arr, axis=target_dim))

    def clamp(self, min=None, max=None):
        return MockTensor(np.clip(self, min, max))

    def mean(self, dim=None, keepdim=False):
        return MockTensor(super().mean(axis=dim, keepdims=keepdim))

    def std(self, dim=None, keepdim=False):
        return MockTensor(super().std(axis=dim, keepdims=keepdim))

    def sum(self, dim=None, keepdim=False):
        return MockTensor(super().sum(axis=dim, keepdims=keepdim))

    def abs(self):
        return MockTensor(np.abs(self))

    def sqrt(self):
        return MockTensor(np.sqrt(self))

    def contiguous(self):
        return self

    def detach(self):
        return self

    def numpy(self):
        return np.asarray(self)


class MockNNFunctional:
    @staticmethod
    def interpolate(input, size=None, scale_factor=None, mode="nearest", align_corners=None):
        arr = np.asarray(input)
        if size is not None:
            if isinstance(size, int):
                target_shape = arr.shape[:-1] + (size,)
            elif isinstance(size, (tuple, list)):
                target_shape = arr.shape[:-len(size)] + tuple(size)
            else:
                target_shape = arr.shape
            return MockTensor(np.resize(arr, target_shape))
        return MockTensor(arr)

    @staticmethod
    def pad(input, pad, mode="constant", value=0.0):
        arr = np.asarray(input)
        np_pad = [(0, 0)] * arr.ndim
        num_pad_dims = len(pad) // 2
        for i in range(num_pad_dims):
            dim_idx = arr.ndim - 1 - i
            np_pad[dim_idx] = (pad[2 * i], pad[2 * i + 1])
        padded = np.pad(arr, np_pad, mode=mode, constant_values=value)
        return MockTensor(padded)

    @staticmethod
    def avg_pool2d(input, kernel_size=5, stride=1, padding=0):
        arr = np.asarray(input)
        return MockTensor(arr)


class MockTorchModule:
    float32 = "float32"
    float16 = "float16"
    int64 = "int64"
    Tensor = MockTensor
    nn = MagicMock()

    def __init__(self):
        self.nn.functional = MockNNFunctional()

    @staticmethod
    def zeros(*shape, dtype=None, device=None):
        if len(shape) == 1 and isinstance(shape[0], (tuple, list)):
            shape = shape[0]
        return MockTensor(np.zeros(shape, dtype=np.float32))

    @staticmethod
    def ones(*shape, dtype=None, device=None):
        if len(shape) == 1 and isinstance(shape[0], (tuple, list)):
            shape = shape[0]
        return MockTensor(np.ones(shape, dtype=np.float32))

    @staticmethod
    def zeros_like(tensor, dtype=None, device=None):
        return MockTensor(np.zeros_like(np.asarray(tensor), dtype=np.float32))

    @staticmethod
    def ones_like(tensor, dtype=None, device=None):
        return MockTensor(np.ones_like(np.asarray(tensor), dtype=np.float32))

    @staticmethod
    def full(shape, fill_value, dtype=None, device=None):
        if isinstance(shape, (int, float)):
            shape = (int(shape),)
        return MockTensor(np.full(shape, fill_value, dtype=np.float32))

    @staticmethod
    def full_like(tensor, fill_value, dtype=None, device=None):
        return MockTensor(np.full_like(np.asarray(tensor), fill_value, dtype=np.float32))

    @staticmethod
    def tensor(data, dtype=None, device=None):
        return MockTensor(np.array(data, dtype=np.float32))

    @staticmethod
    def from_numpy(data):
        return MockTensor(data)

    @staticmethod
    def cat(tensors, dim=0):
        arrays = [np.asarray(t) for t in tensors]
        return MockTensor(np.concatenate(arrays, axis=dim))

    @staticmethod
    def linspace(start, end, steps, device=None):
        return MockTensor(np.linspace(start, end, steps, dtype=np.float32))

    @staticmethod
    def cos(input):
        return MockTensor(np.cos(np.asarray(input)))

    @staticmethod
    def sin(input):
        return MockTensor(np.sin(np.asarray(input)))

    @staticmethod
    def sqrt(input):
        return MockTensor(np.sqrt(np.asarray(input)))

    @staticmethod
    def mean(input, dim=None, keepdim=False):
        if isinstance(dim, list):
            dim = tuple(dim)
        return MockTensor(np.mean(np.asarray(input), axis=dim, keepdims=keepdim))

    @staticmethod
    def std(input, dim=None, keepdim=False):
        if isinstance(dim, list):
            dim = tuple(dim)
        return MockTensor(np.std(np.asarray(input), axis=dim, keepdims=keepdim))

    @staticmethod
    def sum(input, dim=None, keepdim=False):
        return MockTensor(np.sum(np.asarray(input), axis=dim, keepdims=keepdim))

    @staticmethod
    def abs(input):
        return MockTensor(np.abs(np.asarray(input)))

    @staticmethod
    def clamp(input, min=None, max=None):
        return MockTensor(np.clip(np.asarray(input), min, max))

    @staticmethod
    def max(input, dim=None, keepdim=False):
        if dim is None:
            return MockTensor(np.max(np.asarray(input)))
        return (MockTensor(np.max(np.asarray(input), axis=dim, keepdims=keepdim)), MockTensor(np.argmax(np.asarray(input), axis=dim, keepdims=keepdim)))

    @staticmethod
    def min(input, dim=None, keepdim=False):
        if dim is None:
            return MockTensor(np.min(np.asarray(input)))
        return (MockTensor(np.min(np.asarray(input), axis=dim, keepdims=keepdim)), MockTensor(np.argmin(np.asarray(input), axis=dim, keepdims=keepdim)))

    @staticmethod
    def all(tensor):
        return bool(np.all(tensor))

    @staticmethod
    def any(tensor):
        return bool(np.any(tensor))

    @staticmethod
    def arange(*args, **kwargs):
        return MockTensor(np.arange(*args, dtype=np.float32))

    @staticmethod
    def meshgrid(*tensors, indexing="ij"):
        arrays = [np.asarray(t) for t in tensors]
        res = np.meshgrid(*arrays, indexing=indexing)
        return tuple(MockTensor(r) for r in res)

    @staticmethod
    def save(obj, f):
        import pickle
        if isinstance(f, str):
            with open(f, "wb") as fp:
                pickle.dump(obj, fp)
        else:
            pickle.dump(obj, f)

    @staticmethod
    def load(f, map_location=None, **kwargs):
        import pickle
        if isinstance(f, str):
            with open(f, "rb") as fp:
                return pickle.load(fp)
        return pickle.load(f)


def setup_mock_torch_if_needed():
    """Inject mock torch and comfy modules into sys.modules if not installed."""
    if "comfy" not in sys.modules:
        comfy_mock = MagicMock()
        comfy_mock.nested_tensor.NestedTensor.side_effect = lambda t: t
        sys.modules["comfy"] = comfy_mock
        sys.modules["comfy.sample"] = comfy_mock.sample
        sys.modules["comfy.samplers"] = comfy_mock.samplers
        sys.modules["comfy.nested_tensor"] = comfy_mock.nested_tensor
    try:
        import torch
        return torch
    except ImportError:
        mock = MockTorchModule()
        sys.modules["torch"] = mock
        sys.modules["torch.nn"] = mock.nn
        sys.modules["torch.nn.functional"] = mock.nn.functional
        return mock
