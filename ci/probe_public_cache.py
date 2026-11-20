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
    if evidence["status"] != "found" or evidence["authority"] != "ADVISORY_ONLY":
        raise ValueError("Public example record unavailable")
    first = requests[:]
    requests.clear()
    second = refresh(directory / "osv", fetch)
    shared_records.refresh(directory / "records", fetch)
    urls = [POINTER, *(shared_records.BASE + kind + ".json" for kind in ("history", "knowledge"))]
    if tag != second or requests != [(url, True, 0) for url in urls]:
        raise ValueError("The warm client fetched changed data. Rerun if the release advanced.")
    return tag, first, requests


def history_only_update(directory):
    source = Path(__file__).resolve().parents[1] / "docs/v1/history.json"
    rows = json.loads(source.read_bytes())
    row = next(r for r in rows if (r["package"], r["from"], r["to"]) == ("react-dom", "18.2.0", "18.3.1"))
    row["outcome"] = "failed" if row["outcome"] == "passed" else "passed"
    body = json.dumps(rows).encode()
    requested = []
    def changed(url, limit, etag=None):
        requested.append(url)
        if not etag:
            raise AssertionError("Expected a warm request, not an asset download")
        return (body, '"simulated-edit"') if url == shared_records.BASE + "history.json" else (None, etag)
    refresh(directory / "osv", changed)
    shared_records.refresh(directory / "records", changed)
    result = shared_records.lookup(directory / "records", row["package"], row["from"], row["to"])
    assert requested == [POINTER, shared_records.BASE + "history.json", shared_records.BASE + "knowledge.json"]
    assert any(observation["outcome"] == row["outcome"] for observation in result["observations"])
    return len(body)


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
                      "warmBytes": [n for _, _, n in first[2]], "profiles": 2,
                      "simulatedHistoryEditBytes": history_only_update(work / "two"), "simulatedOsvBytes": 0}))
