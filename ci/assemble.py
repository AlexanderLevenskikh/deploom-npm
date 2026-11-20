"""Build an offline Windows npm package in a fresh directory (build Python 3.14+)."""
import argparse
import csv
import io
import hashlib
import json
import shutil
import tarfile
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


def python_runtime(archive, runtime, notices):
    roots = {"python.exe", "python3.dll", "python312.dll", "vcruntime140.dll", "vcruntime140_1.dll", "LICENSE.txt"}
    omit = {"site-packages", "__pycache__", "test", "tests", "tkinter", "idlelib", "ensurepip", "turtledemo"}
    with tarfile.open(checked(archive, LOCK["python"]["sha256"]), mode="r|zst") as source:
        for entry in source:
            if entry.isdir():
                continue
            path = parts(entry.name)
            if path[:2] == ["python", "licenses"]:
                dest = notices.joinpath(*path[2:])
            elif path[:2] == ["python", "install"]:
                rel = path[2:]
                if not rel or rel[0] not in roots | {"Lib", "DLLs"} or omit.intersection(rel):
                    continue
                if rel[-1].endswith((".pyc", ".pdb")) or (rel[0] == "DLLs" and
                        (rel[-1].startswith(("_test", "_tkinter", "tk86", "tcl86")) or rel[-1] == "_ctypes_test.pyd")):
                    continue
                dest = runtime.joinpath(*rel)
            else:
                continue
            if not entry.isfile():
                raise ValueError(f"Unsupported archive entry: {entry.name}")
            with source.extractfile(entry) as stream:
                copy_member(stream, dest)
    for license_name in ("cpython", "openssl-3", "libffi", "sqlite", "zlib", "expat", "bzip2", "liblzma", "mpdecimal"):
        if not (notices / f"LICENSE.{license_name}.txt").is_file():
            raise ValueError(f"Missing bundled Python notice: {license_name}")


def install_wheel(wheel, runtime, notices):
    site = runtime / "Lib/site-packages"
    installed_notices = []
    # The upstream Windows wheel also embeds Linux and macOS binaries.
    omitted = set()
    if wheel.name.startswith("z3_solver-") and wheel.name.endswith("-win_amd64.whl"):
        with zipfile.ZipFile(wheel) as archive:
            omitted = {n for n in archive.namelist() if n.startswith("z3/lib/libz3") and
                       (".so" in n or n.endswith(".dylib"))}
    with zipfile.ZipFile(wheel) as archive:
        for member in archive.infolist():
            if member.is_dir() or member.filename in omitted:
                continue
            rel = parts(member.filename)
            if rel[0].endswith(".data"):
                bases = {"data": runtime, "purelib": site, "platlib": site, "scripts": runtime / "Scripts"}
                target = bases[rel[1]].joinpath(*rel[2:])
            else:
                target = site.joinpath(*rel)
            if omitted and member.filename.endswith(".dist-info/RECORD"):
                rows = csv.reader(io.StringIO(archive.read(member).decode("utf-8")))
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("x", encoding="utf-8", newline="") as stream:
                    csv.writer(stream, lineterminator="\n").writerows(row for row in rows if row[0] not in omitted)
            else:
                with archive.open(member) as src:
                    copy_member(src, target)
            basename = rel[-1].lower()
            if ("licenses" in rel or basename.startswith(("license", "licence", "copying", "copyright", "notice"))):
                out = notices.joinpath(*rel)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(target, out)
                installed_notices.append(out)
    if not installed_notices:
        if wheel.name != "z3_solver-4.13.0.0-py2.py3-none-win_amd64.whl":
            raise ValueError(f"No license found: {wheel.name}")
        notices.mkdir(parents=True)
        shutil.copyfile(ROOT / "licenses/z3-4.13.0.txt", notices / "LICENSE.txt")


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
        install_wheel(wheel, runtime, notices / record["name"])
    install_wheel(checked(args.mcp_wheel, args.mcp_sha256), runtime, notices / "deploom-mcp")
    release = json.loads((runtime / "Lib/site-packages/deploom_mcp/resources/release-manifest.json").read_bytes())
    version = json.loads((package / "package.json").read_bytes())["version"]
    manifest = {"schema": 1, "cliVersion": version, "python": LOCK["python"], "mcpWheelSha256": args.mcp_sha256,
                "mcpVersion": release["mcpVersion"], "coreRevision": release["core"]["revision"],
                "coreVersion": release["core"]["version"], "blueprintSchemaVersion": release["blueprintSchemaVersion"],
                "skill": release["skill"], "wheels": LOCK["wheels"],
                "files": [{"name": p.relative_to(runtime).as_posix(), "sha256": digest(p)}
                          for p in sorted(runtime.rglob("*")) if p.is_file()]}
    (package / "runtime-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("python-archive", "wheelhouse", "mcp-wheel", "output"):
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
