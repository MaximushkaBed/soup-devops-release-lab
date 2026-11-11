"""Small LoRA projection with a frozen base and the standard zero B initialization."""

import torch

from .activation import reference, swiglu


class LoRAProjection(torch.nn.Module):
    def __init__(self, inputs=7, outputs=11, rank=3):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.randn(outputs, inputs) * 0.2, requires_grad=False)
        self.a = torch.nn.Parameter(torch.randn(rank, inputs) * 0.1)
        self.b = torch.nn.Parameter(torch.zeros(outputs, rank))
        self.scale = 2.0 / rank

    def forward(self, x):
        adapter = (x @ self.a.T) @ self.b.T  # ADAPTER_PATH
        return x @ self.weight.T + self.scale * adapter


class TinyLoRA(torch.nn.Module):
    def __init__(self, backend="cpu", block=256, oracle=False):
        super().__init__()
        self.up, self.gate = LoRAProjection(), LoRAProjection()
        self.backend, self.block, self.oracle = backend, block, oracle

    def forward(self, x):
        if self.oracle:

            def projection(layer):
                return torch.nn.functional.linear(x, layer.weight) + layer.scale * (
                    torch.nn.functional.linear(torch.nn.functional.linear(x, layer.a), layer.b)
                )

            return reference(projection(self.up), projection(self.gate))
        up, gate = self.up(x), self.gate(x)
        return swiglu(up, gate, self.backend, self.block)
