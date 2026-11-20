"""Build an npm advisory index from an official OSV ecosystem export."""
import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from urllib.request import urlopen
import zipfile

SOURCE = "https://osv-vulnerabilities.storage.googleapis.com/npm/all.zip"
MAX_ZIP = 800_000_000


def rows(advisory):
    if advisory.get("withdrawn"):
        return
    for item in advisory["affected"]:
        package = item.get("package")
        if package is None and item.get("ranges") and all(r["type"] == "GIT" for r in item["ranges"]):
            continue
        if package["ecosystem"] != "npm":
            continue
        ranges = [[r["type"], r["events"]] for r in item.get("ranges", [])]
        yield (package["name"], advisory["id"], (advisory.get("database_specific") or {}).get("severity"),
               json.dumps(item.get("versions", []), separators=(",", ":")),
               json.dumps(ranges, separators=(",", ":")))


def build_index(source, published, destination):
    """Expose the completed directory in one rename. Existing revisions are preserved."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        work = Path(temporary)
        output = work / "release"
        output.mkdir()
        database = work / "npm.sqlite"
        connection = sqlite3.connect(database)
        try:
            connection.execute("CREATE TABLE advisory (name TEXT NOT NULL, id TEXT NOT NULL, severity TEXT, versions TEXT, ranges TEXT)")
            with zipfile.ZipFile(source) as archive:
                members = sorted(archive.infolist(), key=lambda m: m.filename)
                if sum(m.file_size for m in members) > 4_000_000_000:
                    raise ValueError("OSV export exceeds unpacked budget")
                for member in members:
                    if member.is_dir():
                        continue
                    if not member.filename.endswith(".json") or member.file_size > 32_000_000:
                        raise ValueError("Invalid OSV export member")
                    connection.executemany("INSERT INTO advisory VALUES (?, ?, ?, ?, ?)", rows(json.loads(archive.read(member))))
            connection.execute("CREATE INDEX by_package ON advisory(name)")
            connection.execute("PRAGMA user_version=1")
            connection.commit()
            count, = connection.execute("SELECT COUNT(*) FROM advisory").fetchone()
            if not count or connection.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise ValueError("Unusable OSV index")
        finally:
            connection.close()
        compressed = output / "npm.sqlite.gz"
        with database.open("rb") as db, compressed.open("wb") as target:
            with gzip.GzipFile(filename="", mode="wb", fileobj=target, mtime=0, compresslevel=6) as gz:
                shutil.copyfileobj(db, gz)
        with compressed.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        name = f"npm-{digest}.sqlite.gz"
        compressed.rename(output / name)
        manifest = dict(schema=1, ecosystem="npm", source=SOURCE, published=published, expires=published + 7*86400,
                        sha256=digest, size=(output / name).stat().st_size, unpacked=database.stat().st_size,
                        rows=count, asset=name, tag=f"osv-{published}-{digest[:16]}")
        (output / "manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
        output.rename(destination)
    return manifest


def download(destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=destination.parent) as raw, urlopen(SOURCE, timeout=120) as response:
        published = int(parsedate_to_datetime(response.headers["Last-Modified"]).timestamp())
        age = datetime.now(timezone.utc).timestamp() - published
        if not -300 <= age < 7 * 86400:
            raise ValueError("OSV export is outside freshness policy")
        while chunk := response.read(1024 * 1024):
            if raw.tell() + len(chunk) > MAX_ZIP:
                raise ValueError("OSV download exceeds budget")
            raw.write(chunk)
        return build_index(raw, published, destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    print(json.dumps(download(parser.parse_args().destination), sort_keys=True))
