"""Build Pages from reviewed small datasets and the latest immutable OSV release."""
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from probe_pages import RELEASES, get

REPO = "levencode-labs/deploom-npm"
TAG = re.compile(r"osv-([0-9]{1,12})-([a-f0-9]{16})")


def select_release(releases):
    candidates = []
    for release in releases:
        match = TAG.fullmatch(release["tag_name"])
        if match and release.get("immutable") and not release["draft"] and not release["prerelease"]:
            candidates.append((int(match[1]), release["tag_name"]))
    if not candidates:
        raise ValueError("No immutable OSV release")
    date, tag = max(candidates)
    if len({name for epoch, name in candidates if epoch == date}) != 1:
        raise ValueError("Conflicting editions have the same source timestamp")
    return tag


def prepare(destination):
    root = Path(__file__).resolve().parents[1]
    pages = json.loads(subprocess.check_output(["gh", "api", "--paginate", "--slurp",
                        f"repos/{REPO}/releases?per_page=100"]))
    tag = select_release(release for page in pages for release in page)
    base = RELEASES + tag + "/"
    raw, _ = get(base + "manifest.json", 8192)
    manifest = json.loads(raw)
    sha = manifest["sha256"]
    if (manifest["schema"] != 1 or manifest["ecosystem"] != "npm" or not re.fullmatch("[a-f0-9]{64}", sha)
            or manifest["tag"] != tag or tag != f"osv-{manifest['published']}-{sha[:16]}"
            or manifest["source"] != "https://osv-vulnerabilities.storage.googleapis.com/npm/all.zip"
            or manifest["asset"] != f"npm-{sha}.sqlite.gz" or not 0 < manifest["size"] <= 64_000_000):
        raise ValueError("Unrecognized OSV release manifest")
    blob, _ = get(base + manifest["asset"], manifest["size"])
    if len(blob) != manifest["size"] or hashlib.sha256(blob).hexdigest() != sha:
        raise ValueError("Released OSV asset does not match manifest")
    work = destination.parent / "readback"
    work.mkdir(parents=True, exist_ok=True)
    for name, data in (("manifest.json", raw), (manifest["asset"], blob)):
        file = work / name
        file.write_bytes(data)
        subprocess.run(["gh", "attestation", "verify", str(file), "--repo", REPO,
                        "--signer-workflow", REPO + "/.github/workflows/osv-release.yml"], check=True)
    shutil.copytree(root / "docs", destination)
    pointer = dict(schema=1, tag=tag, manifest=base + "manifest.json", sha256=hashlib.sha256(raw).hexdigest())
    (destination / "v1/osv.json").write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    prepare(Path(sys.argv[1]))
