"""Copy CPython's build metadata and the license texts it names into the offline archive."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

archive, triple, digest, destination = sys.argv[1:]
archive = Path(archive)
url = ("https://github.com/astral-sh/python-build-standalone/releases/download/20261110/"
       f"cpython-3.13.18%2B20261110-{triple}-pgo%2Blto-full.tar.zst")
subprocess.run(["curl", "-fsSL", "--retry", "3", "--proto", "=https", "--proto-redir", "=https",
                "-o", str(archive), url], check=True)
with archive.open("rb") as stream:
    if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
        raise ValueError("Full CPython distribution digest mismatch")
root = archive.parent / "python"
subprocess.run(["tar", "-xf", str(archive), "-C", str(archive.parent)], check=True)
metadata = json.loads((root / "PYTHON.json").read_bytes())
if metadata["target_triple"] != triple:
    raise ValueError("Full CPython distribution target mismatch")
destination = Path(destination)
destination.mkdir()
shutil.copy2(root / "PYTHON.json", destination)
paths = {metadata["license_path"]}
for variants in metadata["build_info"]["extensions"].values():
    for extension in variants:
        paths.update(extension.get("license_paths", []))
        value = extension.get("license_path", [])
        paths.update([value] if isinstance(value, str) else value)
for path in sorted(paths):
    source = (root / path).resolve(strict=True)
    source.relative_to(root.resolve())
    out = destination / source.relative_to(root.resolve())
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, out)
if (root / "licenses").is_dir():
    shutil.copytree(root / "licenses", destination / "licenses", dirs_exist_ok=True)
