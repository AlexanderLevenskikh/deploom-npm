"""Verify an immutable DepLoom release and save its provenance for offline import."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlsplit
from urllib.request import urlopen

REPO = "levencode-labs/deploom-npm"
SIGNER = REPO + "/.github/workflows/publish-npm.yml"


def collect(version, dest):
    tag = "npm-v" + version

    def gh(*command):
        return subprocess.check_output(["gh", *command], cwd=dest)

    release = json.loads(gh("api", f"repos/{REPO}/releases/tags/{tag}"))
    if release.get("immutable") is not True or release["tag_name"] != tag:
        raise ValueError("Release is not immutable or tag differs")
    assets = {asset["name"]: asset for asset in release["assets"]}
    gh("release", "download", tag, "--repo", REPO, "--pattern", "upstream.json")
    trust = dest / "github-trusted-root.jsonl"
    trust.write_bytes(gh("attestation", "trusted-root"))

    def verify(file, algorithm, bundle):
        gh("attestation", "verify", file.name, "--repo", REPO, "--digest-alg", algorithm,
           "--bundle", str(bundle), "--custom-trusted-root", str(trust),
           "--signer-workflow", SIGNER, "--source-ref", "refs/tags/" + tag)

    def verify_asset(file):
        with file.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if assets[file.name]["digest"] != "sha256:" + digest or file.stat().st_size != assets[file.name]["size"]:
            raise ValueError(f"Asset differs from immutable release: {file.name}")
        gh("attestation", "download", file.name, "--repo", REPO)
        bundles = [p for p in dest.glob("sha256*.jsonl") if p.stem[7:] == digest]
        if len(bundles) != 1:
            raise ValueError(f"Missing attestation for {file.name}")
        verify(file, "sha256", bundles[0])
        bundles[0].rename(dest / f"sha256-{digest}.jsonl")

    manifest = dest / "upstream.json"
    verify_asset(manifest)
    data = json.loads(manifest.read_bytes())
    if (data["repository"], data["name"], data["version"], data["schema"]) != (REPO, "@levencode/deploom", version, 1):
        raise ValueError("Upstream identity differs from release")
    primary = f"levencode-deploom-{version}.tgz"
    if data["tarball"] != primary:
        raise ValueError("Unexpected registry archive name")
    archives = [(primary, data)]
    for entry in data.get("platformArchives", []):
        target = entry["platform"]
        if target not in {"linux-x64", "linux-arm64", "darwin-arm64"} or entry["tarball"] != f"deploom-{target}-{version}.tgz":
            raise ValueError("Unexpected offline archive")
        archives.append((entry["tarball"], entry))
    if len(set(name for name, _ in archives)) != len(archives) or {name for name in assets if name.endswith(".tgz")} != {name for name, _ in archives}:
        raise ValueError("Archive list differs from immutable release")
    for name, entry in archives:
        gh("release", "download", tag, "--repo", REPO, "--pattern", name)
        file = dest / name
        verify_asset(file)
        with file.open("rb") as stream:
            integrity = "sha512-" + base64.b64encode(hashlib.file_digest(stream, "sha512").digest()).decode()
        if integrity != entry["integrity"] or file.stat().st_size != entry["bytes"]:
            raise ValueError(f"Archive differs from upstream contract: {name}")
    with urlopen("https://registry.npmjs.org/@levencode%2fdeploom/" + version, timeout=30) as response:
        dist = json.load(response)["dist"]
    url = urlsplit(dist["attestations"]["url"])
    if dist["integrity"] != data["integrity"] or (url.scheme, url.netloc) != ("https", "registry.npmjs.org"):
        raise ValueError("npm registry integrity or attestation origin differs")
    with urlopen(url.geturl(), timeout=30) as response:
        attestations = json.load(response)["attestations"]
    provenance, = [a["bundle"] for a in attestations if a["predicateType"] == "https://slsa.dev/provenance/v1"]
    npm_bundle = dest / "npm-provenance.json"
    npm_bundle.write_text(json.dumps(provenance) + "\n", encoding="utf-8")
    verify(dest / primary, "sha512", npm_bundle)
    print(f"Verified {len(archives)} archive(s), signed upstream contract and npm provenance for {tag}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", args.version):
        raise ValueError("Expected an exact release version")
    dest = args.output.resolve()
    if dest.exists():
        raise FileExistsError(f"Choose a fresh output directory: {dest}")
    with tempfile.TemporaryDirectory(dir=dest.parent) as work:
        stage = Path(work) / "verified"
        stage.mkdir()
        collect(args.version, stage)
        stage.rename(dest)


if __name__ == "__main__":
    main()
