"""Render the two-page submission from verified Actions evidence (needs reportlab)."""

import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parent


def render() -> None:
    proof = json.loads((ROOT / "proofs.json").read_text())
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "Text", fontName="Helvetica", fontSize=10, leading=13, spaceAfter=7, alignment=TA_LEFT
        )
    )
    styles["Heading1"].fontSize = 19
    styles["Heading1"].leading = 23
    styles["Heading1"].textColor = colors.HexColor("#163047")
    styles["Heading2"].fontSize = 12
    styles["Heading2"].leading = 16
    styles["Heading2"].spaceBefore = 8
    story = []

    def p(text: str, style: str = "Text") -> None:
        story.append(Paragraph(text, styles[style]))

    def link(url: str, label: str) -> str:
        return f'<a color="#075985" href="{escape(url)}">{escape(label)}</a>'

    p("Soup DevOps release pipeline", "Heading1")
    p("Maksim | 10 November 2026 | Evidence and verdict")
    p(
        "A green source test is insufficient: the distribution must work after installation. "
        "This repository builds a dependency-free greeting CLI, deliberately breaks four "
        "independent "
        "release properties, and validates the published candidate on Windows and Ubuntu, "
        "CPython 3.10-3.14. " + link(proof["repository"], "Private repository") + "."
    )
    p("Four controlled incidents", "Heading2")
    descriptions = {
        "python310": (
            "Python compatibility",
            "Import datetime.UTC (introduced in 3.11) while "
            "advertising 3.10 support. Both 3.10 artifact jobs fail with ImportError; "
            "the other eight combinations pass.",
        ),
        "windows": (
            "OS portability",
            "Replace getpass with the Unix-only pwd module. All five "
            "Windows artifact jobs fail with ModuleNotFoundError; Linux passes.",
        ),
        "missing-data": (
            "Packaging completeness",
            "Exclude greeting.txt from package data. "
            "Tests in src still see it; installed wheel and rebuilt sdist raise "
            "FileNotFoundError on all ten targets, and Docker fails.",
        ),
        "entrypoint": (
            "Console entry point",
            "Point the script at missing_main. Calling main() "
            "in unit tests still works; the installed command raises ImportError "
            "on all ten targets, and Docker fails.",
        ),
    }
    for fault, (title, detail) in descriptions.items():
        item = proof["incidents"][fault]
        p(
            f"<b>{title}.</b> {detail} "
            + link(item["naive"], "Naive: GREEN")
            + " / "
            + link(item["hardened"], "Hardened: RED")
            + "."
        )
    p(
        "The injector prints an exact diff against a clean checkout; the same commit is used "
        "for each pair. Naive CI tests source on Linux 3.12, builds, and checks metadata. "
        "The hardened path exercises the installed console command, not just importability. "
        "All original failed runs remain available in docs/evidence.md."
    )
    p("What the corrected pipeline verifies", "Heading2")
    p(
        "Lint and unit tests precede one wheel/sdist build using hash-locked tools. The wheel is "
        "built from the sdist. Ten OS/Python jobs install the wheel and independently rebuild the "
        "sdist in a builder, then test it in another clean runtime. Runtimes exclude the checkout "
        "and bootstrap packages. Docker installs the same wheel and runs non-root, offline and "
        "read-only. " + link(proof["fixed"], "Corrected matrix: GREEN") + "."
    )
    p(
        "On a matching tag reachable from main, only the publisher receives OIDC permission in "
        "the tag-restricted testpypi environment. It uploads the tested bytes without rebuilding. "
        "A final job checks both file hashes served by TestPyPI and performs a fresh, "
        "hash-checked index installation. "
        + link(proof["publish"], "Release and index check: GREEN")
        + "; "
        + link(proof["package"], "TestPyPI 0.9.3")
        + "."
    )

    story.append(PageBreak())
    p("Trust boundaries, costs and limitations", "Heading1")
    p("Silent failures addressed", "Heading2")
    p(
        "<b>Dependencies:</b> no runtime dependencies; unexpected Requires-Dist is rejected. "
        "Build tools and transitive requirements use exact versions and hashes; Actions and the "
        "Docker base use immutable references. These choices reduce moving inputs, but hashes "
        "cannot establish that a selected dependency is benign."
    )
    p(
        "<b>Cache and stale artifacts:</b> no environment or resolver cache is restored. Fresh "
        "runtime venvs cannot borrow build dependencies. Commit, run ID, attempt, version and "
        "both distribution hashes are bound in a manifest. Every consumer verifies the same "
        "immutable upload; negative checks reject tampering, a stale commit and a wrong tag."
    )
    p(
        "<b>Privilege and version:</b> PR jobs have read-only permissions, no publisher secrets, "
        "no persisted checkout credentials, and no privileged PR event. OIDC exists only in the "
        "tag-only publish job. A version/tag mismatch fails before upload. These controls target "
        "high-impact failures without buying GPU time or adding runtime dependencies."
    )
    p("GPU design and monthly estimate", "Heading2")
    p(
        "GPU testing is a design only: this CPU-only CLI has no useful GPU behavior to validate. "
        "For a future GPU feature, use a Runpod Secure Cloud RTX 4090 at $0.89/hour, checked "
        "10 November 2026. Assume 30 nightlies at 10 minutes, four releases at 20 minutes, and "
        "two minutes overhead per run: 7.47 hours, $6.65 compute. Prorated disposable 20 GB disk "
        "adds about $0.02; a 25% allowance gives <b>$8.33/month</b>. Excludes tax, egress and "
        "GitHub minutes. " + link("https://www.runpod.io/pricing", "Provider prices") + "."
    )
    p(
        "Run only after CPU gates, on isolated ephemeral workers. A broker validates GitHub OIDC "
        "and keeps the provider key out of workloads. Reserve worst-case lease cost, "
        "cap concurrency "
        "and hourly price, enforce a $10 monthly cap, and use an external watchdog to terminate "
        "Pods and disks at 15/30-minute limits even after Actions cancellation. "
        "No paid GPU was rented."
    )
    p("Verdict: not ready for unattended real PyPI", "Heading2")
    p(
        "Automatic TestPyPI publication is demonstrated. Before real PyPI, protect main "
        "and release "
        "tags, require review of workflow/lock changes, and add tests for the actual application's "
        "contracts. Green does not prove absence of malicious code, vulnerable pinned tools or "
        "account compromise. macOS, ARM, PyPy and unusual user environments are untested. "
        "Post-publication verification can detect failure only after upload. Yank a bad release "
        "and publish a new version; this cannot recall existing installations or mirrored files."
    )
    p("Surprise and remaining concern", "Heading2")
    p(
        "The strongest surprise was that valid metadata, a successful build and passing source "
        "tests all coexisted with an unusable installed command. Even importing the package would "
        "miss the broken entry point. The remaining concern is the workflow's own trust boundary: "
        "a compromised maintainer can change both code and checks, then tag a malicious release."
    )
    p("AI usage and personal verification", "Heading2")
    p(
        "Codex drafted code, workflows and prose and executed the automated checks. "
        "Review corrected "
        "YAML quoting, Docker context exclusions, hidden bootstrap dependencies, "
        "optimization-sensitive "
        "assertions and initially suppressed CLI stderr. " + proof["personal_verification"]
    )

    def footer(canvas, doc):
        canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
        canvas.line(40, 36, A4[0] - 40, 36)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#475569"))
        canvas.drawString(40, 23, "Soup DevOps take-home | Full logs and limitations in repository")
        canvas.drawRightString(A4[0] - 40, 23, f"{doc.page}/2")

    target = ROOT / "submission.pdf"
    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=35,
        bottomMargin=45,
        title="Soup DevOps - release pipeline evidence and verdict",
        author="Maksim",
    )
    story.append(Spacer(1, 1))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(target)


if __name__ == "__main__":
    render()
