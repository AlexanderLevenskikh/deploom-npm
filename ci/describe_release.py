"""Bind the tested tarball to the released Core, MCP, Skill and data contracts."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("wheel_lock", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    upstream = json.loads(args.wheel_lock.read_bytes())
    with tarfile.open(args.archive) as archive:
        pkg = json.load(archive.extractfile("package/package.json"))
        runtime = json.load(archive.extractfile("package/runtime-manifest.json"))
    if (pkg["name"] != "@levencode/deploom" or pkg["version"] != runtime["cliVersion"]
            or runtime["mcpWheelSha256"] != upstream["sha256"] or runtime["mcpVersion"] != upstream["version"]
            or runtime["coreRevision"] != upstream["coreRevision"]
            or os.environ["GITHUB_REF_NAME"] != "npm-v" + pkg["version"]):
        raise ValueError("Package identity does not match reviewed release inputs and tag")
    with args.archive.open("rb") as stream:
        integrity = hashlib.file_digest(stream, "sha512").digest()
    result = dict(schema=1, name=pkg["name"], version=pkg["version"], tarball=args.archive.name,
                  integrity="sha512-" + base64.b64encode(integrity).decode(), bytes=args.archive.stat().st_size,
                  repository="levencode-labs/deploom-npm", commit=os.environ["GITHUB_SHA"],
                  platform="win32-x64", python=runtime["python"], coreRevision=runtime["coreRevision"],
                  coreVersion=runtime["coreVersion"], mcp=upstream, skill=runtime["skill"],
                  solverSha256=runtime["solverSha256"],
                  dataSchemas={"osv": 1, "history": 1, "knowledge": 1}, blueprintSchema=runtime["blueprintSchemaVersion"])
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
