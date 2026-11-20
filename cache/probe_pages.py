"""Check the deployed public cache from an anonymous client."""
import gzip
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "https://levencode-labs.github.io/deploom-npm/v1/"
RELEASES = "https://github.com/levencode-labs/deploom-npm/releases/download/"


def get(url, limit):
    with urlopen(url, timeout=60) as response:
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError("Response exceeds limit")
        return data, response.headers.get("ETag")


def main():
    snapshots = {}
    for name in ("osv", "history", "knowledge"):
        url = BASE + name + ".json"
        body, etag = get(url, 2_000_000)
        snapshots[name] = json.loads(body)
        if not etag:
            raise ValueError("Missing ETag for " + name)
        try:
            with urlopen(Request(url, headers={"If-None-Match": etag}), timeout=30) as second:
                raise ValueError(f"{name} conditional GET returned {second.status}")
        except HTTPError as response:
            with response:
                if response.code != 304 or response.read(1):
                    raise
        print(f"{name}: {len(body)} bytes, repeat 304 with empty body")
    pointer = snapshots["osv"]
    release = RELEASES + pointer["tag"] + "/"
    if pointer["manifest"] != release + "manifest.json":
        raise ValueError("Unexpected manifest location")
    raw, _ = get(pointer["manifest"], 8192)
    if hashlib.sha256(raw).hexdigest() != pointer["sha256"]:
        raise ValueError("Manifest digest mismatch")
    manifest = json.loads(raw)
    if manifest["tag"] != pointer["tag"] or manifest["asset"] != f"npm-{manifest['sha256']}.sqlite.gz":
        raise ValueError("Release identity mismatch")
    data, _ = get(release + manifest["asset"], 64_000_000)
    if len(data) != manifest["size"] or hashlib.sha256(data).hexdigest() != manifest["sha256"]:
        raise ValueError("OSV digest or size mismatch")
    import io
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        unpacked = stream.read(128_000_001)
    if len(unpacked) > 128_000_000 or len(unpacked) != manifest["unpacked"]:
        raise ValueError("Invalid database size")
    with tempfile.TemporaryDirectory() as tmp:
        database = Path(tmp) / "index.sqlite"
        database.write_bytes(unpacked)
        db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
        try:
            if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise ValueError("SQLite integrity check failed")
            count, = db.execute("SELECT count(*) FROM advisory").fetchone()
            if count != manifest["rows"] or count <= 0:
                raise ValueError("Wrong advisory count")
        finally:
            db.close()
    print(f"{pointer['tag']}: {len(data)} compressed bytes, {count} rows, verified")


if __name__ == "__main__":
    main()
