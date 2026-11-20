"""Fetch checksum-locked public inputs. Existing files must match the same digest."""
import argparse
import json
import os
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from assemble import LOCK, checked


def fetch(url, output, expected):
    if output.exists():
        checked(output, expected)
        return
    with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as stream:
        part = Path(stream.name)
    try:
        with urlopen(url, timeout=90) as response, part.open("wb") as stream:
            shutil.copyfileobj(response, stream)
        checked(part, expected)
        os.replace(part, output)
    finally:
        part.unlink(missing_ok=True)


def wheel(record):
    name, version, filename = (record[key] for key in ("name", "version", "filename"))
    with urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=30) as response:
        entries = json.load(response)["urls"]
    matches = [e for e in entries if e["filename"] == filename and e["digests"]["sha256"] == record["sha256"]]
    if len(matches) != 1:
        raise ValueError(f"PyPI has no matching locked wheel for {name}=={version}")
    url = matches[0]["url"]
    if (urlparse(url).scheme, urlparse(url).hostname) != ("https", "files.pythonhosted.org"):
        raise ValueError(f"Unexpected wheel host for {name}")
    fetch(url, args.output / filename, record["sha256"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as threads:
        list(threads.map(wheel, LOCK["wheels"]))
    fetch(LOCK["python"]["url"], args.output / "cpython.tar.zst", LOCK["python"]["sha256"])
    print(f"Verified {len(LOCK['wheels'])} public wheels and CPython {LOCK['python']['version']}")
