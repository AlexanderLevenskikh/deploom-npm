"""Install the pinned OpenCode executable for native CI in a private test directory."""
import hashlib
import os
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import shutil
import zipfile

host = {"darwin": "darwin", "linux": "linux"}[sys.platform]
arch = {"x86_64": "x64", "aarch64": "arm64", "arm64": "arm64"}[platform.machine()]
target = host + "-" + arch
digests = {
    "darwin-arm64": "25ba9908979fa7d764792c82589b4b5768ab1511154e0317d98aa77d216ce767",
    "linux-arm64": "5a528f42caf576c6cdece6a191eb273d3db54effa5518e0402684d8f8026aeb6",
    "linux-x64": "09f44302c10fd036912f59c81fd1aef5df45dd06f649197f9dfc9bbe2a79614e",
}
name = "opencode-" + target + (".zip" if host == "darwin" else ".tar.gz")
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
archive = Path(os.environ["RUNNER_TEMP"]) / name
url = "https://github.com/anomalyco/opencode/releases/download/v2.2.5/" + name
subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error", "--retry", "3", "-o", archive, url], check=True)
with archive.open("rb") as stream:
    if hashlib.file_digest(stream, "sha256").hexdigest() != digests[target]:
        raise ValueError("OpenCode digest mismatch")
with (out / "opencode").open("xb") as dest:
    if host == "darwin":
        with zipfile.ZipFile(archive) as z:
            member, = [n for n in z.namelist() if Path(n).name == "opencode"]
            with z.open(member) as source:
                shutil.copyfileobj(source, dest)
    else:
        with tarfile.open(archive) as tar:
            member, = [m for m in tar if m.isfile() and Path(m.name).name == "opencode"]
            with tar.extractfile(member) as source:
                shutil.copyfileobj(source, dest)
(out / "opencode").chmod(0o755)
