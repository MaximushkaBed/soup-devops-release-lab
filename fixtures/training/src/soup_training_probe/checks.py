"""Contracts check derivatives and updates, not merely a decreasing loss."""

import copy

import torch

from .activation import reference, swiglu
from .errors import ContractError
from .model import TinyLoRA


def close(actual, expected, tolerance, code, detail):
    try:
        torch.testing.assert_close(actual, expected, **tolerance, equal_nan=False)
    except AssertionError as error:
        raise ContractError(code, f"{detail}: {error}") from error


def forward_check(backend, block, tolerance, device):
    torch.manual_seed(107)
    candidate = TinyLoRA(backend, block).to(device)
    oracle = copy.deepcopy(candidate)
    oracle.oracle = True
    x = torch.randn(7, 3, device=device).T
    with torch.no_grad():
        close(candidate(x), oracle(x), tolerance, "forward-mismatch", "LoRA forward")
    return {"name": "forward", "status": "passed", "shape": [3, 11]}


def activation_checks(backend, contract, device):
    # BF16 interpreter limitations are an explicit scope, not a successful GPU test.
    dtypes = (
        [torch.float32]
        if backend == "interpreter"
        else [
            torch.float32,
            torch.float16,
            torch.bfloat16,
        ]
    )
    cases = []
    for dtype in dtypes:
        name = str(dtype).removeprefix("torch.")
        tolerance = contract["tolerances"][name]
        for n in (0, 1, 7, 257, 1025):
            # The stride-two views exercise a layout that is not contiguous.
            x = torch.linspace(-8, 8, 2 * n, dtype=torch.float32, device=device).to(dtype)[::2]
            gate = torch.linspace(0.25, 1.25, 2 * n, device=device).to(dtype)[::2]
            x = x.detach().requires_grad_(True)
            gate = gate.detach().requires_grad_(True)
            xr, gr = (
                x.detach().clone().requires_grad_(True),
                gate.detach().clone().requires_grad_(True),
            )
            output = swiglu(x, gate, backend, contract["block_size"])
            expected = reference(xr, gr)
            close(output, expected, tolerance, "forward-mismatch", f"{backend} {name} n={n}")
            weights = torch.linspace(0.1, 1.0, n, device=device)
            (output.float() * weights).sum().backward()
            (expected.float() * weights).sum().backward()
            close(x.grad, xr.grad, tolerance, "gradient-mismatch", f"dX {name} n={n}")
            close(gate.grad, gr.grad, tolerance, "gradient-mismatch", f"dGate {name} n={n}")
            cases.append({"dtype": name, "elements": n})
    if backend == "cpu":
        torch.manual_seed(109)
        x = torch.randn(2, 3, dtype=torch.float64, requires_grad=True)
        gate = torch.randn(2, 3, dtype=torch.float64, requires_grad=True)
        try:
            torch.autograd.gradcheck(lambda a, b: swiglu(a, b), (x, gate), fast_mode=True)
        except (AssertionError, RuntimeError) as error:
            raise ContractError(
                "gradient-mismatch", f"Finite-difference gradcheck: {error}"
            ) from error
    return {
        "name": "activation-forward-backward",
        "status": "passed",
        "cases": cases,
        "finite_difference": backend == "cpu",
    }


def training_check(backend, contract, device):
    torch.manual_seed(113)
    candidate = TinyLoRA(backend, contract["block_size"]).to(device)
    oracle = copy.deepcopy(candidate)
    oracle.oracle = True
    frozen = {
        name: p.detach().clone() for name, p in candidate.named_parameters() if not p.requires_grad
    }
    expected_trainable = {"up.a", "up.b", "gate.a", "gate.b"}
    if {name for name, p in candidate.named_parameters() if p.requires_grad} != expected_trainable:
        raise ContractError("trainable-set-mismatch", "Only LoRA A/B may be trainable")
    optimizer = torch.optim.SGD([p for p in candidate.parameters() if p.requires_grad], lr=0.05)
    reference_optimizer = torch.optim.SGD(
        [p for p in oracle.parameters() if p.requires_grad], lr=0.05
    )
    x = torch.randn(7, 3, device=device).T
    target = torch.randn(3, 11, device=device) * 0.2
    tolerance = contract["tolerances"]["float32"]
    losses = []
    for step in range(2):
        optimizer.zero_grad(set_to_none=True)
        reference_optimizer.zero_grad(set_to_none=True)
        actual, expected = candidate(x), oracle(x)
        close(actual, expected, tolerance, "forward-mismatch", f"training step {step}")
        loss = torch.nn.functional.mse_loss(actual, target)
        reference_loss = torch.nn.functional.mse_loss(expected, target)
        loss.backward()
        reference_loss.backward()
        for name, parameter in candidate.named_parameters():
            if name in frozen:
                if parameter.grad is not None or not torch.equal(parameter.detach(), frozen[name]):
                    raise ContractError("frozen-base-changed", name)
                continue
            expected_gradient = dict(oracle.named_parameters())[name].grad
            if parameter.grad is None or expected_gradient is None:
                raise ContractError("adapter-gradient-missing", f"{name}, step {step}")
            # Zero A gradients in the first step are valid when LoRA B starts at zero.
            close(
                parameter.grad,
                expected_gradient,
                tolerance,
                "gradient-mismatch",
                f"{name}, step {step}",
            )
        optimizer.step()
        reference_optimizer.step()
        for name, parameter in candidate.named_parameters():
            close(
                parameter,
                dict(oracle.named_parameters())[name],
                tolerance,
                "update-mismatch",
                f"{name}, step {step}",
            )
            if name in frozen and not torch.equal(parameter.detach(), frozen[name]):
                raise ContractError("frozen-base-changed", name)
        losses.append(float(loss.detach().cpu()))
    if all(
        torch.count_nonzero(p.detach()) == 0
        for name, p in candidate.named_parameters()
        if name.endswith(".b")
    ):
        raise ContractError("adapter-update-missing", "No LoRA B update occurred")
    return {
        "name": "lora-two-step",
        "status": "passed",
        "steps": 2,
        "losses": losses,
        "frozen_base": "unchanged",
        "zero_initialized_b": True,
    }
