"""Masked SwiGLU kernels: compilation/execution is separate from CPU interpretation."""

import triton
import triton.language as tl


@triton.jit
def forward_kernel(X, G, Y, N: tl.constexpr, BLOCK: tl.constexpr):
    offsets = tl.program_id(0) * BLOCK + tl.arange(0, BLOCK)
    mask = offsets < N  # TAIL_MASK
    x = tl.load(X + offsets, mask, other=0).to(tl.float32)
    gate = tl.load(G + offsets, mask, other=0).to(tl.float32)
    sigmoid = 1.0 / (1.0 + tl.exp(-x))
    tl.store(Y + offsets, x * sigmoid * gate, mask)


@triton.jit
def backward_kernel(DY, X, G, DX, DG, N: tl.constexpr, BLOCK: tl.constexpr):
    offsets = tl.program_id(0) * BLOCK + tl.arange(0, BLOCK)
    mask = offsets < N
    x = tl.load(X + offsets, mask, other=0).to(tl.float32)
    gate = tl.load(G + offsets, mask, other=0).to(tl.float32)
    dy = tl.load(DY + offsets, mask, other=0).to(tl.float32)
    sigmoid = 1.0 / (1.0 + tl.exp(-x))
    derivative = sigmoid + x * sigmoid * (1.0 - sigmoid)
    tl.store(DX + offsets, dy * gate * derivative, mask)
    tl.store(DG + offsets, dy * x * sigmoid, mask)


def launch_forward(x, gate, block):
    import torch

    x, gate = x.contiguous(), gate.contiguous()
    # A sentinel makes missing tail stores deterministic in correctness runs.
    output = torch.full_like(x, float("nan"))
    if x.numel():
        forward_kernel[(triton.cdiv(x.numel(), block),)](x, gate, output, x.numel(), block)
    return output


def launch_backward(dy, x, gate, block):
    import torch

    dy, x, gate = dy.contiguous(), x.contiguous(), gate.contiguous()
    dx, dg = torch.full_like(x, float("nan")), torch.full_like(gate, float("nan"))
    if x.numel():
        backward_kernel[(triton.cdiv(x.numel(), block),)](dy, x, gate, dx, dg, x.numel(), block)
    return dx, dg
