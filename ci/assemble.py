"""Build an offline Windows npm package in a fresh directory (build Python 3.14+)."""
import argparse
import base64
import csv
import io
import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "ci/windows-x64.lock.json").read_bytes())


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checked(path, expected):
    if digest(path) != expected:
        raise ValueError(f"SHA-256 mismatch: {path.name}")
    return path


def parts(name):
    items = name.split("/")
    if any(not s or s in {".", ".."} or "\\" in s or ":" in s for s in items):
        raise ValueError(f"Unexpected archive path: {name}")
    return items


def copy_member(stream, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as output:
        shutil.copyfileobj(stream, output)


def unpack(archive, directory):
    with zipfile.ZipFile(archive) as source:
        for entry in source.infolist():
            if not entry.is_dir():
                with source.open(entry) as stream:
                    copy_member(stream, directory.joinpath(*parts(entry.filename)))


def python_runtime(archive, runtime, notices):
    python = LOCK["python"]
    unpack(checked(archive, python["sha256"]), runtime)
    bundle = ROOT / "licenses" / python["notices"]
    unpack(checked(bundle, python["noticesSha256"]), notices)
    shutil.copyfile(runtime / "LICENSE.txt", notices / "LICENSE.txt")
    # The PSF embeddable distribution documents this file as the application's search path.
    pth, = runtime.glob("python*._pth")
    config = pth.read_bytes()
    marker = b"#import site"
    if config.count(marker) != 1:
        raise ValueError("Unexpected embeddable interpreter path configuration")
    pth.write_bytes(config.replace(marker, b"Lib/site-packages\r\nLib/site-packages/deploom_mcp/_core\r\nimport site"))


def install_wheel(wheel, runtime, notices, solver=None):
    site = runtime / "Lib/site-packages"
    installed_notices = []
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        omitted = set()
        replacements = {}
        if solver:
            exe, = (n for n in names if n.endswith(".data/data/bin/z3.exe"))
            replacements = {"z3/lib/libz3.dll": solver / "libz3.dll", exe: solver / "z3.exe"}
            omitted = {n for n in names if n.startswith("z3/lib/") and n not in replacements}
        elif wheel.name.startswith("pywin32-"):
            # The GUI and the Exchange MAPI extensions use additional Microsoft libraries.
            omitted = {n for n in names if n.startswith(("pythonwin/", "win32comext/mapi/"))}
        for member in archive.infolist():
            name = member.filename
            if member.is_dir() or name in omitted:
                continue
            rel = parts(name)
            if rel[0].endswith(".data"):
                bases = {"data": runtime, "purelib": site, "platlib": site, "scripts": runtime / "Scripts"}
                target = bases[rel[1]].joinpath(*rel[2:])
            else:
                target = site.joinpath(*rel)
            if (omitted or replacements) and name.endswith(".dist-info/RECORD"):
                rows = csv.reader(io.StringIO(archive.read(member).decode("utf-8")))
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("x", encoding="utf-8", newline="") as stream:
                    writer = csv.writer(stream, lineterminator="\n")
                    for row in rows:
                        if row[0] in replacements:
                            source = replacements[row[0]]
                            checksum = base64.urlsafe_b64encode(bytes.fromhex(digest(source))).decode().rstrip("=")
                            row = [row[0], "sha256=" + checksum, str(source.stat().st_size)]
                        if row[0] not in omitted:
                            writer.writerow(row)
            elif name in replacements:
                with replacements[name].open("rb") as stream:
                    copy_member(stream, target)
            else:
                with archive.open(member) as stream:
                    copy_member(stream, target)
            if "licenses" in rel or rel[-1].lower().startswith(("license", "licence", "copying", "copyright", "notice")):
                out = notices.joinpath(*rel)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(target, out)
                installed_notices.append(out)
        for name in sorted(omitted):
            if name.lower().endswith("/license.txt"):
                with archive.open(name) as stream:
                    copy_member(stream, notices.joinpath(*parts(name)))
    if solver:
        notices.mkdir(parents=True, exist_ok=True)
        for name in ("Z3-LICENSE.txt", "MinGW-COPYRIGHT.txt", "GCC-GPL-3.txt", "GCC-COPYRIGHT.txt",
                     "GCC-RUNTIME-EXCEPTION.txt", "compiler-copyright.txt", "BUILD-INFO.txt"):
            shutil.copyfile(solver / name, notices / name)
    elif not installed_notices:
        raise ValueError(f"No license found: {wheel.name}")


def assemble(args, package):
    runtime = package / "runtime"
    notices = package / "THIRD_PARTY_NOTICES"
    for name in ("package.json", "LICENSE", "README.md"):
        shutil.copyfile(ROOT / name, package / name)
    for name in ("bin", "vendor"):
        shutil.copytree(ROOT / name, package / name)
    python_runtime(args.python_archive, runtime, notices / "CPython")
    for record in LOCK["wheels"]:
        wheel = checked(args.wheelhouse / record["filename"], record["sha256"])
        install_wheel(wheel, runtime, notices / record["name"], args.solver if record["name"] == "z3-solver" else None)
    install_wheel(checked(args.mcp_wheel, args.mcp_sha256), runtime, notices / "deploom-mcp")
    vc_runtime = re.compile(r"(?:vcruntime|msvcp|mfc|vcomp|concrt)\d.*\.dll", re.IGNORECASE)
    vc_files = {p.relative_to(runtime).as_posix().lower() for p in runtime.rglob("*.dll") if vc_runtime.fullmatch(p.name)}
    if vc_files != {"vcruntime140.dll", "vcruntime140_1.dll"}:
        raise ValueError(f"Unexpected stand-alone Visual C++ runtime files: {sorted(vc_files)}")
    release = json.loads((runtime / "Lib/site-packages/deploom_mcp/resources/release-manifest.json").read_bytes())
    version = json.loads((package / "package.json").read_bytes())["version"]
    manifest = {"schema": 1, "cliVersion": version, "python": LOCK["python"], "mcpWheelSha256": args.mcp_sha256,
                "mcpVersion": release["mcpVersion"], "coreRevision": release["core"]["revision"],
                "solverSha256": {name: digest(args.solver / name) for name in ("libz3.dll", "z3.exe")},
                "coreVersion": release["core"]["version"], "blueprintSchemaVersion": release["blueprintSchemaVersion"],
                "skill": release["skill"], "wheels": LOCK["wheels"],
                "files": [{"name": p.relative_to(runtime).as_posix(), "sha256": digest(p)}
                          for p in sorted(runtime.rglob("*")) if p.is_file()]}
    (package / "runtime-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("python-archive", "wheelhouse", "solver", "mcp-wheel", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--mcp-sha256", required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output directory must be new")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.output.parent) as stage:
        package = Path(stage) / "package"
        package.mkdir()
        assemble(args, package)
        package.rename(args.output)
