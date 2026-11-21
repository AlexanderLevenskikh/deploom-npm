"""Expand release files for static scanning without running npm or loading any package."""
import argparse
import json
import re
from email.parser import BytesHeaderParser
import shutil
import tarfile
from pathlib import Path, PurePosixPath


def unpack(archive, destination):
    destination.mkdir()
    total = 0
    with tarfile.open(archive, "r:gz") as source:
        for member in source:
            # Links carry no file contents. Scan each regular member at its own path.
            if member.isdir() or member.issym() or member.islnk():
                continue
            path = PurePosixPath(member.name)
            if (not member.isfile() or path.is_absolute() or ".." in path.parts
                    or "\\" in member.name or ":" in member.name):
                raise ValueError("Unsafe archive member: " + member.name)
            total += member.size
            if total > 2 * 1024**3:
                raise ValueError("Archive exceeds scan size limit")
            target = destination.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.extractfile(member) as reader, target.open("xb") as writer:
                shutil.copyfileobj(reader, writer)


def inventory(directory):
    """Describe the exact Python and vendored npm components to Trivy's lockfile analyzers."""
    python = set()
    for path in directory.rglob("*.dist-info/METADATA"):
        meta = BytesHeaderParser().parsebytes(path.read_bytes())
        name, version = meta["Name"], meta["Version"]
        if not name or not version or not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or not re.fullmatch(r"[A-Za-z0-9_.+!-]+", version):
            raise ValueError("Invalid distribution metadata in " + str(path))
        python.add((name, version))
    npm = {}
    for path in directory.rglob("package.json"):
        meta = json.loads(path.read_bytes())
        name, version = meta.get("name"), meta.get("version")
        if name and version:
            key = "node_modules/" + name
            if key in npm and npm[key]["version"] != version:
                key = "node_modules/" + path.parent.relative_to(directory).as_posix() + "/" + key
            npm[key] = {"name": name, "version": version}
    if not any(name.replace("_", "-").lower() == "deploom-mcp" for name, _ in python):
        raise ValueError("Installed MCP distribution missing from " + str(directory))
    if not any(p["name"] == "jsonc-parser" for p in npm.values()):
        raise ValueError("Vendored npm dependency missing from " + str(directory))
    dest = directory / "scan-inventory"
    dest.mkdir()
    (dest / "requirements.txt").write_text("".join(f"{n}=={v}\n" for n,v in sorted(python)), encoding="utf-8")
    npm_packages = dict(npm, **{"": {"dependencies": {x["name"]:x["version"] for x in npm.values()}}})
    lock = {"name": "inspected-archive", "version": "0.0.0", "lockfileVersion": 3, "packages": npm_packages}
    (dest / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")
    return {"requirements.txt": sorted(python), "package-lock.json": sorted({(x["name"],x["version"]) for x in npm.values()})}


def check_report(root, path):
    results = json.loads(path.read_bytes())["Results"]
    expected = json.loads((root / "scan-inventory.json").read_bytes())
    if len(expected) != 4:
        raise ValueError("Expected inventories for four platforms")
    for directory, locks in expected.items():
        for file, entries in locks.items():
            filename = directory + "/scan-inventory/" + file
            rows = [r for r in results if r["Target"].replace("\\", "/").endswith(filename)]
            if len(rows) != 1:
                raise ValueError("Missing or ambiguous scanner inventory: " + filename)
            def package_id(name, version):
                if file == "requirements.txt":
                    name = re.sub(r"[-_.]+", "-", name.lower())
                return name, version
            found = {package_id(pkg["Name"], pkg["Version"]) for pkg in rows[0].get("Packages", [])}
            missing = {package_id(n, v) for n, v in entries} - found
            if missing:
                raise ValueError(f"{filename}: scanner missed {sorted(missing)}")
            print(f"{filename}: {len(found)} package versions checked")
    failures = set()
    for result in results:
        for v in result.get("Vulnerabilities", []):
            failures.add((v["VulnerabilityID"],v["PkgName"],v["InstalledVersion"],v.get("FixedVersion","")))
        for secret in result.get("Secrets", []):
            failures.add(("secret",secret["RuleID"],result["Target"],""))
    for finding in sorted(failures):
        print(" | ".join(finding))
    if failures:
        raise SystemExit("High or critical package/security findings require review")


def prepare(archives, output):
    output.mkdir()
    targets = set()
    inventories = {}
    for archive in sorted(archives.glob("*.tgz")):
        dest = output / archive.stem
        unpack(archive, dest)
        package = dest / "package"
        meta = json.loads((package / "package.json").read_bytes())
        if "deploomPlatforms" in meta:  # Corporate selector contains only its JS launcher.
            continue
        upstream = package / "upstream.tgz"
        if upstream.is_file():
            unpack(upstream, dest / "upstream")
            package = dest / "upstream/package"
        portable = package / "portable-runtime.tar.gz"
        if portable.is_file():
            unpack(portable, dest / "runtime")
            target = meta["os"][0] + "-" + meta["cpu"][0]
        else:
            target = "win32-x64"
        if target in targets:
            raise ValueError("Duplicate platform archive: " + archive.name)
        inventories[dest.name] = inventory(dest)
        targets.add(target)
    if targets != {"win32-x64", "linux-x64", "linux-arm64", "darwin-arm64"}:
        raise ValueError("Incomplete scan, found platforms: " + ", ".join(sorted(targets)))
    (output / "scan-inventory.json").write_text(json.dumps(inventories), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path, help="Validate Trivy scan coverage and findings")
    args = parser.parse_args()
    if args.report:
        check_report(args.output, args.report)
    else:
        prepare(args.archives, args.output)
