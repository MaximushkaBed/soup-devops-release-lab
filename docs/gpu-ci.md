# Native GPU CI design (not executed)

The greeting CLI is CPU-only. The separate [training fixture](training-contracts.md) implements
a native CUDA SwiGLU/LoRA probe alongside CPU and Triton-interpreter contracts. Interpretation
cannot validate compiled GPU kernels. No native GPU test was executed; this design describes
the remaining provisioning and budget controls.

## When and what

For every release: CPU lint, source tests, artifact matrix and image checks pass first; then a
20-minute GPU budget tests the exact candidate artifact plus the supported CUDA/driver combination.
Check `nvidia-smi`, device discovery, installed `soup-training-probe --backend cuda`,
OOM/error handling, and actual application behavior. Record GPU model, driver, CUDA, image digest,
artifact SHA and results. Gate publication on its success once GPU support is advertised.

Nightly at 02:00 UTC: run a 10-minute regression on protected main, including a slightly larger
fixture and numeric tolerances. Use one concurrent lease, cancel obsolete nightly work, and keep
release leases separate. A red nightly blocks the next release until triaged. Do not run a GPU
matrix across ten CPU combinations: select the supported GPU platform deliberately.

## Provider and monthly assumptions

Use one Runpod Secure Cloud RTX 4090 (24 GB). The provider's public price checked 2026-11-10 is
$0.89/GPU-hour; attached CPU/RAM are included in that listed Pod configuration. Choose Secure Cloud
for the controlled host fleet; 24 GB is an explicit workload assumption, not a measured requirement.
Assume a 30-day month, 30 nightlies, four releases, and two extra minutes per run for provisioning,
image pulls and teardown. Billable time = (30×10 + 4×20 + 34×2)/60 = 7.47 hours, or **$6.65 compute**.
A disposable 20 GB container disk at $0.10/GB/month, prorated for 7.47 of 720 hours, adds about $0.02.
A 25% contingency gives **about $8.33/month**. No persistent disk, snapshots or idle Pod are retained;
egress, tax, retries beyond the allowance and GitHub Actions minutes are excluded. Rates, stock,
image-start time and the necessary GPU memory must be checked before deployment.

## Avoid paying for broken or abandoned runs

Use a broker rather than installing a permanent self-hosted runner. The broker validates GitHub
OIDC repository/ref claims, accepts only a successful CPU-gate artifact digest, and holds the
Runpod API key outside test containers. Runpod itself is not assumed to accept GitHub OIDC.
Launch an ephemeral non-root container by digest; do not pass publishing or provider credentials.
Fork PRs cannot acquire leases. Use no privileged Docker socket, runner reuse, or shared writable
cache across trust boundaries.

The broker records the Pod ID **before** dispatch. Enforce 15-minute nightly and 30-minute release
lease limits with an external watchdog, in addition to workflow timeouts and `finally` cleanup.
Terminate, rather than merely stop, Pods and delete their volumes. A periodic reconciler removes
orphaned leases even if Actions is canceled or the runner disappears. The broker refuses new leases
when the $10 monthly cap would be exceeded, reserves each lease's worst-case cost before launch,
and caps the hourly rate at $0.89; no silent upgrade to a more expensive GPU. Use billing alerts as
an extra signal, not as the enforcement mechanism. Allow at most one transient provisioning retry;
never automatically retry a failed application test. These controls are a design, not deployed code.

Sources: [Runpod pricing](https://www.runpod.io/pricing),
[Pod lifecycle](https://docs.runpod.io/pods/manage-pods),
[Pod storage](https://docs.runpod.io/pods/storage/types).
