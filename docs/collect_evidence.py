"""Collect actual run metadata and raw logs, preserving every historical run."""

import concurrent.futures
import io
import json
import re
import subprocess
import zipfile
from pathlib import Path

REPO = "MaximushkaBed/soup-devops-release-lab"
ROOT = Path(__file__).resolve().parents[1]
COMMIT = "7fee1977f2b876e7705d4f98c1826dadda126897"
PUBLISH_RUN = 42768719990
FAULTS = ("python310", "windows", "missing-data", "entrypoint")


def gh(*args: str) -> bytes:
    return subprocess.check_output(["gh", *args], cwd=ROOT)


def detail(run: dict) -> dict:
    data = json.loads(gh("run", "view", str(run["databaseId"]), "--json", "jobs"))
    run["jobs"] = [
        {
            "name": job["name"],
            "conclusion": job["conclusion"],
            "status": job["status"],
            "url": job.get("url", ""),
            "failed_steps": [
                step["name"] for step in job["steps"] if step["conclusion"] == "failure"
            ],
        }
        for job in data["jobs"]
    ]
    return run


def archive(run: dict) -> tuple[int, str]:
    runid = run["databaseId"]
    target = ROOT / ".evidence" / f"{runid}.zip"
    if target.exists():
        data = target.read_bytes()
    else:
        data = gh("api", f"repos/{REPO}/actions/runs/{runid}/logs")
        target.write_bytes(data)
    with zipfile.ZipFile(io.BytesIO(data)) as logs:
        text = "\n".join(
            logs.read(name).decode("utf-8-sig", errors="replace")
            for name in logs.namelist()
            if name.endswith(".txt")
        )
    return runid, re.sub(r"\x1b\[[0-9;]*m", "", text)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    runs = json.loads(
        gh(
            "run",
            "list",
            "--limit",
            "100",
            "--json",
            "databaseId,displayTitle,status,conclusion,headSha,url,createdAt",
        )
    )
    selected = {r["displayTitle"]: r for r in reversed(runs) if r["headSha"] == COMMIT}
    release = next(r for r in runs if r["databaseId"] == PUBLISH_RUN)
    primary = [selected["Release checks / main"], release]
    for fault in FAULTS:
        primary.extend([selected[f"Naive / {fault}"], selected[f"Release checks / {fault}"]])
    require(all(r["status"] == "completed" for r in primary), "Primary runs are still in progress")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        details = list(pool.map(detail, runs))
    (ROOT / ".evidence").mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        logs = dict(pool.map(archive, primary))
    by_id = {r["databaseId"]: r for r in details}
    for run in primary[:2]:
        require(run["conclusion"] == "success", f"Fixed/release is not green: {run['url']}")
    require(
        next(j for j in by_id[PUBLISH_RUN]["jobs"] if j["name"] == "verify-index")["conclusion"]
        == "success",
        "Post-publication verification failed",
    )
    prior_path = ROOT / "docs/proofs.json"
    prior = json.loads(prior_path.read_text()) if prior_path.exists() else {}
    proof = {
        "repository": f"https://github.com/{REPO}",
        "commit": COMMIT,
        "fixed": primary[0]["url"],
        "publish": release["url"],
        "package": "https://test.pypi.org/project/soup-release-lab-maximushkabed/0.9.3/",
        "incidents": {},
    }
    if "personal_verification" in prior:
        proof["personal_verification"] = prior["personal_verification"]
    needles = {
        "python310": "ImportError: cannot import name 'UTC'",
        "windows": "ModuleNotFoundError: No module named 'pwd'",
        "missing-data": "FileNotFoundError:",
        "entrypoint": "ImportError: cannot import name 'missing_main'",
    }
    expected_counts = {"python310": 2, "windows": 5, "missing-data": 11, "entrypoint": 11}
    for fault in FAULTS:
        naive = selected[f"Naive / {fault}"]
        hardened = selected[f"Release checks / {fault}"]
        require(naive["conclusion"] == "success", f"Naive is not green: {fault}")
        require(hardened["conclusion"] == "failure", f"Hardened is not red: {fault}")
        jobs = by_id[hardened["databaseId"]]["jobs"]
        failed = [j for j in jobs if j["conclusion"] == "failure"]
        require(len(failed) == expected_counts[fault], f"Unexpected failing jobs: {fault}")
        require(
            next(j for j in jobs if j["name"] == "build")["conclusion"] == "success",
            f"Build must pass before the artifact fails: {fault}",
        )
        text = logs[hardened["databaseId"]]
        require(needles[fault] in text, f"Intended failure is absent from logs: {fault}")
        errors = [line.split("Z ", 1)[-1] for line in text.splitlines() if needles[fault] in line]
        proof["incidents"][fault] = {
            "naive": naive["url"],
            "hardened": hardened["url"],
            "error": errors[0][:240],
            "failed_jobs": [j["name"] for j in failed],
        }
    (ROOT / "docs/runs.json").write_text(json.dumps(details, indent=2) + "\n")
    (ROOT / "docs/proofs.json").write_text(json.dumps(proof, indent=2) + "\n")
    path = ROOT / "docs/evidence.md"
    original = path.read_text()
    prefix = re.split(r"## (?:Actions runs|Primary evidence)", original, maxsplit=1)[0]
    prefix = prefix.replace(
        "Results below will be populated from actual runs.",
        "All conclusions below were collected from the GitHub API.",
    )
    body = ["## Primary evidence", "", f"Demonstration commit: `{COMMIT}`.", ""]
    for fault, item in proof["incidents"].items():
        body.extend(
            [
                f"### {fault}",
                "",
                f"[Naive: green]({item['naive']}) / [Hardened: red]({item['hardened']}).",
                f"Observed: `{item['error']}`.",
                "Failed jobs: " + ", ".join(f"`{j}`" for j in item["failed_jobs"]) + ".",
                "",
            ]
        )
    body.extend(
        [
            "## Corrected version and TestPyPI",
            "",
            f"[Fixed matrix and Docker: green]({proof['fixed']}).",
            f"[Tag v0.9.3: OIDC upload and index check green]({proof['publish']}).",
            f"[Published package]({proof['package']}).",
            "",
            "The tag points to c4ad4a1; the later 7fee197 change only prints a failing CLI's",
            "captured stderr. Package source and packaging configuration are identical.",
            "",
            "## All runs, including the original demonstrations",
            "",
        ]
    )
    for run in details:
        body.append(
            f"- [{run['databaseId']}: {run['displayTitle']}]({run['url']}) - "
            f"{run['conclusion']} (`{run['headSha'][:7]}`)."
        )
    body.extend(
        [
            "",
            "## Unexpected local failures and corrections",
            "",
            "Local actionlint found invalid YAML quoting around :all:. Docker initially failed",
            "because the ignore file excluded the wheel, after a separate sandbox permission",
            "issue writing Buildx state. Those were fixed before the first Actions run.",
            "The first four red runs proved CLI failure but captured its stderr without printing",
            "it. The smoke helper was corrected and all eight comparisons were repeated so the",
            "original ImportError/ModuleNotFoundError/FileNotFoundError is visible. The initial",
            "runs remain linked above; no failures were deleted or changed to green.",
            "",
            "Machine-readable metadata is in runs.json; selected links/errors are in proofs.json.",
            "Raw primary-run log archives are in the local .evidence directory and submission ZIP.",
            "Artifacts have a 30-day retention period; exported logs remain in the submission ZIP.",
            "",
        ]
    )
    path.write_text(prefix + "\n".join(body))
    print("Validated", len(primary), "primary runs; preserved", len(details), "historical runs")


if __name__ == "__main__":
    main()
