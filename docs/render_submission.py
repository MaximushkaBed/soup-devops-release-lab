"""Render the two-page note; only verified execution is described as passed."""

import io
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate

ROOT = Path(__file__).resolve().parent


class TwoPageDocument(SimpleDocTemplate):
    def afterPage(self):
        if self.page > 2:
            raise ValueError("Submission exceeds two pages")


def render():
    proof = json.loads((ROOT / "proofs.json").read_text())
    previous = json.loads((ROOT / "iteration-2-evidence.json").read_text())
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle("Text", fontName="Helvetica", fontSize=9.5, leading=12.5, spaceAfter=7)
    )
    styles["Heading1"].fontSize, styles["Heading1"].leading = 18, 22
    styles["Heading1"].textColor = colors.HexColor("#163047")
    styles["Heading2"].fontSize, styles["Heading2"].leading = 12, 15
    story = []

    def p(text, style="Text"):
        story.append(Paragraph(text, styles[style]))

    def link(url, label):
        return f'<a color="#075985" href="{escape(url)}">{escape(label)}</a>'

    repo = proof["repository"]
    p("Soup DevOps: release and training contracts", "Heading1")
    p("Maksim | 11 November 2026 | Two-page evidence note")
    p(
        "A passing source test does not establish that an installed package works, or that its "
        "backward pass trains the intended weights. This exercise retains a published greeting CLI "
        "as the release baseline and adds an independently written LoRA/Triton fixture relevant to "
        "Soup's post-training work. " + link(repo, "Public repository") + "."
    )
    p("Original release failures, demonstrated in Actions", "Heading2")
    descriptions = {
        "python310": "Import datetime.UTC while claiming Python 3.10 support: both 3.10 jobs fail.",
        "windows": "Import Unix-only pwd: all five Windows jobs fail.",
        "missing-data": "Omit greeting.txt: installed wheel, rebuilt sdist and Docker fail.",
        "entrypoint": (
            "Point the script at missing_main: source main() passes, installed CLI fails."
        ),
    }
    for fault, detail in descriptions.items():
        item = previous["incidents"][fault]
        p(
            f"<b>{escape(fault)}.</b> {detail} "
            + link(item["naive"], "Naive GREEN")
            + " / "
            + link(item["hardened"], "Installed RED")
            + "."
        )
    p(
        "The corrected baseline passes Ubuntu/Windows x Python 3.10-3.14, testing the wheel and "
        "independently rebuilt sdist in isolated runtimes. Docker "
        "executes the same wheel non-root, "
        "offline and read-only. "
        + link(previous["fixed"], "Corrected matrix")
        + "; "
        + link(proof["publish"], "OIDC publication and index verification")
        + "; "
        + link(proof["package"], "TestPyPI 0.9.3")
        + ". Its immutable tag and published bytes are preserved."
    )
    p("Training contracts: why this is useful for Soup", "Heading2")
    p(
        "Soup's "
        + link("https://trysoup.dev/about", "engineering story")
        + " describes a gradient bug that survived releases. A decreasing loss or correct forward "
        "value is therefore insufficient. The new fixture compares custom SwiGLU forward/backward "
        "with native autograd, adds FP64 finite-difference gradcheck, and compares two LoRA SGD "
        "steps with independent functional.linear projections. Frozen weights must remain exact; "
        "all A/B gradients and updates must match. Zero first-step A gradients are valid when B "
        "starts at zero, but absent gradients fail."
    )
    p(
        "Four injected faults each pass naive CPU source forward: a missing derivative term, "
        "detached LoRA A, omitted kernel-contract.json, and a Triton "
        "tail-mask error. Strong installed "
        "wheel and rebuilt-sdist checks reject every fault for its specific cause. Local execution "
        "verified all <b>17 comparisons</b>; arbitrary build/import "
        "errors cannot satisfy a negative "
        "case. Original failure logs and distribution bytes are retained."
    )
    p(
        "Two pinned stacks passed local CPU and real Triton-interpreter "
        "checks: <b>PyTorch 2.6.0+cpu / "
        "Triton 3.2.0</b> and <b>PyTorch 2.14.0+cpu / Triton 3.8.0</b>. CPU checks include "
        "FP32/FP16/BF16, empty/strided inputs and irregular tails; interpretation is FP32 only. "
        "Independent training CI covers six Linux Python 3.11-3.13/stack combinations "
        "and two Windows Python "
        "3.12/stack combinations, plus bare CLI checks without ML imports. "
        + link(repo + "/actions/workflows/ml-contracts.yml", "Training CI results")
        + "; "
        + link(
            repo + "/blob/main/docs/training-contracts.md", "Contracts and reproducible commands"
        )
        + "."
    )
    story.append(PageBreak())
    p("Trust, GPU boundary and release verdict", "Heading1")
    p("What the pipeline can establish", "Heading2")
    p(
        "<b>Artifact identity:</b> one build creates a wheel from sdist. Commit, run ID, attempt, "
        "distribution digests and profile hashes are bound in a manifest. Consumers verify it; "
        "sdists are also rebuilt independently. Installed probes run outside the checkout with "
        "isolated, optimized Python. RECORD hashes, allowed wheel files, source/resource bytes and "
        "entry points are checked. Stale reports or incomplete numerical reports fail. No restored "
        "environment cache or editable source installation is used."
    )
    p(
        "<b>Dependency provenance:</b> ML CPU wheels use reviewed official PyTorch URLs/SHA256s; "
        "Triton and transitive tools use hashed locks. Downloads are verified before offline "
        "installation, avoiding a mixed extra index and multi-GB CUDA downloads. Exact inventory "
        "and pip check verify the selected closure. Setuptools is "
        "explicit where Torch requires it. "
        "Historical HTTPX/Tenacity experiments remain separate; a weekly/manual canary resolves "
        "fresh supported dependencies and records their versions without updating release locks."
    )
    p(
        "<b>Privileges:</b> PR jobs are read-only, with pinned Actions and no persisted checkout "
        "credentials or publisher secrets. Only a matching tag on main "
        "can publish the tested bytes "
        "through OIDC after the success-only release-ready gate. ML tests run separately. "
        "Registry verification "
        "checks served hashes and a clean install after publication. Corruption fails immediately; "
        "transient registry availability receives bounded retries."
    )
    p("Native GPU: implemented probe, unverified execution", "Heading2")
    p(
        "The separate fixture implements --backend cuda for NVIDIA SM80+: real device discovery, "
        "Triton forward/backward, numerical/LoRA contracts and synchronization before success. "
        "Interpreter mode cannot record native CUDA success. CPU workers were checked to fail "
        "with gpu-unavailable, exit 3 and native_cuda=false. <b>No native GPU run, compiled-kernel "
        "correctness, sanitizer result, memory saving or speedup is claimed.</b> Pin a separate "
        "CUDA/driver/image profile and execute installed artifacts there "
        "before advertising a GPU gate."
    )
    p("GPU budget proposal", "Heading2")
    p(
        "Runpod Secure Cloud RTX 4090: $0.89/hour, checked 10 November 2026. Thirty 10-minute "
        "nightlies, four 20-minute releases and two minutes provisioning/teardown per run total "
        "7.47 hours: $6.65 compute; prorated disposable 20 GB disk about "
        "$0.02; with 25% allowance, "
        "<b>$8.33/month</b>. Excludes tax, egress and GitHub minutes. "
        + link("https://www.runpod.io/pricing", "Price source")
        + ". No paid GPU was rented."
    )
    p(
        "A proposed broker validates GitHub OIDC, holds provider credentials outside workloads, "
        "reserves worst-case lease cost, caps concurrency/rate and enforces a $10 monthly budget. "
        "An external watchdog terminates Pods and volumes at 15/30-minute limits, including after "
        "Actions cancellation. These controls are designed, not deployed."
    )
    p("Verdict and remaining concern", "Heading2")
    p(
        "TestPyPI publication is demonstrated; unattended real PyPI is "
        "not authorized. The repository is public; required checks and branch/tag protection "
        "still require separate configuration. Review workflow/lock changes before "
        "real publishing. "
        "This training fixture is not Soup's production "
        "code or full dependency stack; CUDA, macOS, ARM and unselected versions remain untested. "
        "Pinned hashes do not prove benign code. A compromised maintainer can change both code and "
        "checks; post-upload verification cannot recall installed or mirrored files. Yank a faulty "
        "release and publish a new version."
    )
    p("Surprise and AI disclosure", "Heading2")
    p(
        "The strongest surprise was that a correct forward pass can coexist with broken training: "
        "zero-initialized LoRA B also makes first-step A gradients an "
        "easy false alarm. Codex drafted "
        "and executed the automation; local review corrected YAML quoting and strengthened the "
        "independent oracle and evidence checks. Research subagents compared upstream release "
        "workflows; Claude Code was not used. "
        + proof["personal_verification"]
        + " New training and compatibility checks were AI-assisted; "
        "no new applicant-independent verification or publication is claimed."
    )

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#475569"))
        canvas.drawString(40, 23, "Soup DevOps take-home | Raw evidence and limits in the archive")
        canvas.drawRightString(A4[0] - 40, 23, f"{doc.page}/2")

    buffer = io.BytesIO()
    doc = TwoPageDocument(
        buffer,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=35,
        bottomMargin=40,
        title="Soup DevOps release and training contracts",
        author="Maksim",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    if doc.page != 2:
        raise ValueError(f"Expected two pages, got {doc.page}")
    target = ROOT / "submission.pdf"
    target.write_bytes(buffer.getvalue())
    print(target)


if __name__ == "__main__":
    render()
