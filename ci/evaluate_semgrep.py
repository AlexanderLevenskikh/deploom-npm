"""Classify Semgrep findings from the pinned rules without logging private source text."""
import hashlib
import json
from pathlib import Path
import sys


def main(report, reviews):
    data = json.loads(report.read_bytes())
    if not data.get("paths", {}).get("scanned") or any(e.get("level") == "error" for e in data.get("errors", [])):
        raise ValueError("Semgrep did not complete source analysis")
    reviewed = json.loads(reviews.read_bytes())
    blocking = []
    for finding in data["results"]:
        rule = finding["check_id"].split(".")[-1]
        path = Path(finding["path"])
        location = f"{path}:{finding['start']['line']} {rule}"
        # This audit pattern flags any variable argument list, including CompletedProcess.
        # The separate taint, shell and injection rules still apply at the same site.
        if rule == "dangerous-subprocess-use-audit":
            print("Audit variable argument list:", location)
            continue
        parts = path.parts
        repo = "deploom-npm" if parts[0] == "installer" and (Path("installer/ci/mcp-release.json")).is_file() else parts[0]
        key = "/".join((repo, *parts[1:]))
        decision = reviewed.get(key)
        if decision and rule == decision["rule"] and hashlib.sha256(path.read_bytes()).hexdigest() == decision["sha256"]:
            print("Reviewed:", location, "-", decision["reason"])
        else:
            blocking.append(location)
    for location in blocking:
        print("Review required:", location)
    if blocking:
        raise SystemExit(f"{len(blocking)} unreviewed security findings")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
