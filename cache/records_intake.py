"""Validate reviewed Git blobs as data. Never check out or execute a contributor's tree."""
import argparse
import json
import hashlib
import os
import re
import subprocess
from functools import lru_cache
from pathlib import Path
from urllib.request import HTTPRedirectHandler, build_opener

from deploom_mcp.record_contract import KINDS, LIMIT, SOURCE, parse, validate

FILES = {f"docs/v1/{kind}.json": kind for kind in KINDS}
MAX_ROWS, MAX_PACKAGES = 10, 3


def git(*args):
    return subprocess.check_output(["git", *args], timeout=60)


def blob(commit, name, limit):
    entry = git("ls-tree", "-z", commit, "--", name)
    if not re.fullmatch(rb"100644 blob [0-9a-f]{40}\t" + re.escape(name.encode()) + rb"\x00", entry):
        raise ValueError("Expected a regular Git data file")
    oid = entry.split(b" ", 2)[2].split(b"\t")[0].decode()
    if int(git("cat-file", "-s", oid)) > limit:
        raise ValueError("Data file too large")
    return git("cat-file", "blob", oid)


class RegistryOnly(HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ValueError("Unexpected npm registry redirect")


@lru_cache(maxsize=512)
def npm_version(package, version):
    with build_opener(RegistryOnly()).open(f"https://registry.npmjs.org/{package}/{version}", timeout=15) as response:
        metadata = parse(response.read(LIMIT + 1))
    if metadata.get("name") != package or metadata.get("version") != version:
        raise ValueError("Registry did not confirm the requested version")


@lru_cache(maxsize=256)
def evidence(base, source):
    revision, name = re.fullmatch(SOURCE, source).groups()
    subprocess.run(["git", "merge-base", "--is-ancestor", revision, base], check=True, timeout=20)
    return blob(revision, name, 12_000).decode("utf-8")


def verify_rows(base, rows):
    for row in rows:
        text = evidence(base, row["source"])
        for version in (row["from"], row["to"]):
            npm_version(row["package"], version)
            if version not in text:
                raise ValueError("The evidence file does not identify both versions")
        if row["package"] not in text:
            raise ValueError("Package missing from the pinned evidence")
        _, name = re.fullmatch(SOURCE, row["source"]).groups()
        receipt = parse(blob(base, name.removesuffix("check.cjs") + "evidence.json", 64_000))
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        claim = {k: v for k, v in row.items() if k not in {"schema", "source"}}
        if receipt.get("fixtureSha256") != digest or claim not in receipt.get("claims", []):
            raise ValueError("No maintainer-reviewed matching fixture outcome")


def additions(before, after):
    def identity(row):
        return json.dumps(row, sort_keys=True, separators=(",", ":"))
    old = {identity(r) for r in before}
    new = {identity(r) for r in after}
    if not old <= new:
        raise ValueError("Edits and removals require maintainer review")
    return [r for r in after if identity(r) not in old]


def inspect_pr(base, head):
    basepoint = git("merge-base", base, head).decode().strip()
    paths = git("diff", "--no-renames", "--name-only", "-z", basepoint, head).split(b"\0")[:-1]
    allowed = {p.encode() for p in FILES}
    if not allowed.intersection(paths):
        return None
    if basepoint != base or set(paths) - allowed:
        raise ValueError("Update this data-only PR against current main or request a manual review")
    rows = []
    for path in paths:
        name = path.decode()
        kind = FILES[name]
        baseline = blob(base, name, LIMIT)
        before = validate(kind, parse(baseline))
        candidate = blob(head, name, LIMIT)
        if len(candidate) > len(baseline) + 12_000:
            raise ValueError("Data delta too large")
        after = validate(kind, parse(candidate))
        if len(after) - len(before) > MAX_ROWS:
            raise ValueError("Too many records")
        rows.extend(additions(before, after))
    if not 0 < len(rows) <= MAX_ROWS or len({r["package"] for r in rows}) > MAX_PACKAGES:
        raise ValueError("Expected 1-10 additions across at most three packages")
    verify_rows(base, rows)
    return [{"record": r, "evidence": evidence(base, r["source"])} for r in rows]


def snapshot(base):
    data = {"schema": 1, "revision": int(git("rev-list", "--first-parent", "--count", base))}
    for path, kind in FILES.items():
        data[kind] = validate(kind, parse(blob(base, path, LIMIT)))
        verify_rows(base, data[kind])
    raw = (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(raw) > LIMIT:
        raise ValueError("Combined cache exceeds the MCP limit")
    return raw


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--head")
    args = parser.parse_args()
    for revision in (args.base, args.head):
        if revision is not None and not re.fullmatch("[0-9a-f]{40}", revision):
            parser.error("Invalid commit identity")
    if args.head:
        report = inspect_pr(args.base, args.head)
        if report is not None:
            args.destination.write_text(json.dumps(report), encoding="utf-8")
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            print("eligible=" + ("true" if report is not None else "false"), file=output)
    else:
        args.destination.write_bytes(snapshot(args.base))
