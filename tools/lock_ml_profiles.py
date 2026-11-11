"""Refresh reviewed CPU PyTorch/Triton wheel URLs and SHA256s without downloading CUDA."""

import hashlib
import json
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILES = {"floor": ("2.6.0", "3.2.0"), "modern": ("2.14.0", "3.8.0")}


def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attributes):
        if tag == "a":
            self.links.extend(value for key, value in attributes if key == "href")


def main():
    parser = Links()
    parser.feed(fetch("https://download.pytorch.org/whl/cpu/torch/").decode())
    catalog = {"schema": 1, "profiles": {}}
    for name, (torch, triton) in PROFILES.items():
        wheels = {}
        for minor in (11, 12, 13):
            abi = f"cp3{minor}"
            for system, suffix in (("linux", "x86_64.whl"), ("win32", "win_amd64.whl")):
                matches = [
                    url
                    for url in parser.links
                    if urllib.parse.unquote(url.split("/")[-1]).startswith(
                        f"torch-{torch}+cpu-{abi}-{abi}-"
                    )
                    and urllib.parse.urldefrag(url)[0].endswith(suffix)
                ]
                if len(matches) != 1:
                    raise ValueError(f"Expected one CPU wheel for {name}/{abi}/{system}: {matches}")
                url, fragment = urllib.parse.urldefrag(matches[0])
                if urllib.parse.urlparse(url).hostname not in (
                    "download.pytorch.org",
                    "download-r2.pytorch.org",
                ) or not re.fullmatch(r"sha256=[a-f0-9]{64}", fragment):
                    raise ValueError("Unexpected wheel origin or hash")
                wheels[f"3.{minor}-{system}"] = {"url": url, "sha256": fragment[7:]}
        release = json.loads(fetch(f"https://pypi.org/pypi/triton/{triton}/json"))
        triton_wheels = {}
        for minor in (11, 12, 13):
            matches = [
                item
                for item in release["urls"]
                if f"-cp3{minor}-cp3{minor}-" in item["filename"]
                and item["filename"].endswith("x86_64.whl")
                and not item["yanked"]
            ]
            if len(matches) != 1:
                raise ValueError(f"Expected one Triton wheel: {name}/3.{minor}")
            item = matches[0]
            triton_wheels[f"3.{minor}-linux"] = {
                "url": item["url"],
                "sha256": item["digests"]["sha256"],
            }
        # CPU metadata provides an auditable dependency list without a multi-GB CUDA download.
        metadata = fetch(wheels["3.11-linux"]["url"] + ".metadata")
        catalog["profiles"][name] = {
            "torch": torch + "+cpu",
            "triton": triton,
            "torch_metadata_sha256": hashlib.sha256(metadata).hexdigest(),
            "torch_requires_dist": re.findall(r"^Requires-Dist: (.*)$", metadata.decode(), re.M),
            "torch_wheels": wheels,
            "triton_wheels": triton_wheels,
        }
    target = ROOT / "requirements/ml-wheels.json"
    target.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()
