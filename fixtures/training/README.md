# Training release contract fixture

This separately packaged example exercises a frozen-base LoRA layer and SwiGLU forward/backward.
It is an independently written DevOps test fixture, not Soup's implementation or a production kernel.
The Python 3.11–3.13 scope follows Soup's current product metadata; the original release exercise
retains its separate Python 3.10–3.14 matrix.

The base command starts without importing PyTorch or Triton. Training extras are provisioned from
reviewed, hashed profiles. CPU checks compare gradients and two optimizer steps with independent
PyTorch autograd, including zero-initialized LoRA B. Triton interpreter checks run on CPU and are
explicitly recorded as interpreter evidence. Native CUDA checks require a real supported device.

No GPU throughput, VRAM or CUDA compiler result is implied by a successful CPU/interpreter run.
