"""Explicit custom backward, checked against PyTorch autograd and finite differences."""

import torch


def reference(x, gate):
    work = torch.float64 if x.dtype == torch.float64 else torch.float32
    return (torch.nn.functional.silu(x.to(work)) * gate.to(work)).to(x.dtype)


class SwiGLU(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x, gate, backend, block):
        ctx.save_for_backward(x, gate)
        ctx.backend, ctx.block = backend, block
        if backend == "cpu":
            return reference(x, gate)
        from .kernels import launch_forward

        return launch_forward(x, gate, block)

    @staticmethod
    def backward(ctx, dy):
        x, gate = ctx.saved_tensors
        if ctx.backend != "cpu":
            from .kernels import launch_backward

            dx, dg = launch_backward(dy, x, gate, ctx.block)
        else:
            work = torch.float64 if x.dtype == torch.float64 else torch.float32
            xf, gf, dyf = x.to(work), gate.to(work), dy.to(work)
            sigmoid = torch.sigmoid(xf)
            derivative = sigmoid + xf * sigmoid * (1.0 - sigmoid)  # BACKWARD_DERIVATIVE
            dx = (dyf * gf * derivative).to(x.dtype)
            dg = (dyf * xf * sigmoid).to(gate.dtype)
        return dx, dg, None, None


def swiglu(x, gate, backend="cpu", block=256):
    if x.shape != gate.shape or x.dtype != gate.dtype or x.device != gate.device:
        raise ValueError("SwiGLU inputs must have matching shape, dtype and device")
    return SwiGLU.apply(x, gate, backend, block)
