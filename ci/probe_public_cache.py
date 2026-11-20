"""Read deployed public data twice on independent packaged clients and count bytes."""
import argparse
import json
from pathlib import Path

from deploom_mcp.public_cache import POINTER, get, refresh


def probe(directory):
    requests = []

    def fetch(url, limit, etag=None):
        data, tag = get(url, limit, etag)
        requests.append((url, bool(etag), len(data) if data is not None else 0))
        return data, tag

    tag = refresh(directory, fetch)
    first = requests[:]
    requests.clear()
    second = refresh(directory, fetch)
    if tag != second or requests != [(POINTER, True, 0)]:
        raise ValueError("The warm client fetched changed data. Rerun if the release advanced.")
    return tag, first, requests


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
    print(json.dumps({"tag": first[0], "coldBytes": [n for _, _, n in first[1]],
                      "warmBytes": [n for _, _, n in first[2]], "profiles": 2}))
