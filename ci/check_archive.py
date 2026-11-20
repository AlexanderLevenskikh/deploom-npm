"""Verify every shipped file, compressed archive integrity and offline legal inventory."""
import argparse
import hashlib
import json
import tarfile
from pathlib import Path


def verify(package, archive):
    names = {"LICENSE", "README.md", "package.json", "runtime-manifest.json"}
    for root in ("bin", "runtime", "vendor", "THIRD_PARTY_NOTICES"):
        names.update(p.relative_to(package).as_posix() for p in (package / root).rglob("*") if p.is_file())
    manifest = json.loads((package / "runtime-manifest.json").read_bytes())
    expected_notices = {"CPython", "deploom-mcp", *(w["name"] for w in manifest["wheels"])}
    shipped_notices = set()
    count = 0
    size = 0
    with tarfile.open(archive, mode="r|gz") as tgz:
        for member in tgz:
            if member.isdir():
                continue
            if not member.isfile() or not member.name.startswith("package/"):
                raise ValueError("Unexpected npm archive member")
            name = member.name.removeprefix("package/")
            if name not in names:
                raise ValueError(f"Unexpected or duplicate npm archive member: {name}")
            names.remove(name)
            with tgz.extractfile(member) as packed, (package / name).open("rb") as original:
                if hashlib.file_digest(packed, "sha256").digest() != hashlib.file_digest(original, "sha256").digest():
                    raise ValueError(f"npm pack changed file: {name}")
            if name.startswith("THIRD_PARTY_NOTICES/") and member.size:
                shipped_notices.add(name.split("/")[1])
            count += 1
            size += member.size
    if names or expected_notices != shipped_notices:
        raise ValueError(f"Incomplete package: missing files {sorted(names)}, notice groups {expected_notices - shipped_notices}")
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha512").hexdigest()
    print(json.dumps(dict(files=count, unpacked=size, size=archive.stat().st_size,
                          sha512=digest, notices=len(shipped_notices))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    verify(args.package, args.archive)
