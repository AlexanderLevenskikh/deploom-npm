"""Read deployed public data twice on independent packaged clients and count bytes."""
import argparse
import json
from pathlib import Path

from deploom_mcp.public_cache import POINTER, get, refresh
from deploom_mcp import shared_records


def probe(directory):
    requests = []

    def fetch(url, limit, etag=None):
        data, tag = get(url, limit, etag)
        requests.append((url, bool(etag), len(data) if data is not None else 0))
        return data, tag

    tag = refresh(directory / "osv", fetch)
    shared_records.refresh(directory / "records", fetch)
    evidence = shared_records.lookup(directory / "records", "react-dom", "18.2.0", "18.3.1")
    if evidence["status"] != "found" or evidence["authority"] != "ADVISORY_ONLY" or evidence["snapshotSource"] != "verified-pages":
        raise ValueError("Public example record unavailable")
    first = requests[:]
    requests.clear()
    second = refresh(directory / "osv", fetch)
    shared_records.refresh(directory / "records", fetch)
    urls = [POINTER, shared_records.BASE + "cache.json"]
    if tag != second or requests != [(url, True, 0) for url in urls]:
        raise ValueError("The warm client fetched changed data. Rerun if the release advanced.")
    return tag, first, requests


def tamper_test(directory):
    def changed(url, limit, etag=None):
        if url.endswith("cache.json"):
            return b'{"schema":1,"revision":1,"history":[],"knowledge":[]}', '"unsigned"'
        if url.endswith("cache.sig"):
            return bytes(64), None
        raise AssertionError("Unexpected host or path")
    root = directory / "records"
    if shared_records.refresh(root, changed):
        raise ValueError("Modified snapshot was accepted")
    if shared_records.lookup(root, "react-dom", "18.2.0", "18.3.1")["snapshotSource"] != "bundled":
        raise ValueError("Expected the packaged snapshot")
    if not shared_records.refresh(root):
        raise ValueError("Failed to recover from rejected snapshot")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    work = parser.parse_args().work
    if work.exists():
        parser.error("work directory must be new")
    first = probe(work / "one")
    second = probe(work / "two")
    if first != second:
        raise ValueError("Independent clients differed. Rerun if the release advanced.")
    tamper_test(work / "two")
    print(json.dumps({"tag": first[0], "coldBytes": [n for _, _, n in first[1]],
                      "warmBytes": [n for _, _, n in first[2]], "profiles": 2,
                      "rejectedTamperedSnapshot": True}))
