"""Compare two public React lockfiles with the same target and independent SSR checks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
from statistics import median
import subprocess
from time import perf_counter

from deploom_mcp import public_cache, shared_records
from deploom_mcp.server import get_upgrade_plan


def npm(args, cwd, cache):
    command = [os.environ["ComSpec"], "/d", "/c", "npm.cmd"] if os.name == "nt" else ["npm"]
    subprocess.run([*command, *args, "--cache", str(cache), "--registry=https://registry.npmjs.org/",
                    "--userconfig", str(cache.parent / "user.npmrc"), "--globalconfig", str(cache.parent / "global.npmrc"),
                    "--ignore-scripts", "--no-audit", "--no-fund", "--strict-peer-deps"],
                   cwd=cwd, check=True, capture_output=True, timeout=120)


def fixtures(work):
    hashes = {}
    for project in ("first", "recipient"):
        for version in ("18.2.0", "18.3.1"):
            root = work / project / version
            root.mkdir(parents=True)
            deps = {"react": version, "react-dom": version}
            if project == "recipient":
                deps["semver"] = "7.7.2"
            manifest = {"name": "public-renderer-" + project, "version": "1.0.0", "private": True,
                        "dependencies": deps}
            (root / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
            npm(["install"], root, work / "npm")
            shutil.rmtree(root / "node_modules")
            hashes[project + "/" + version] = hashlib.sha256((root / "package-lock.json").read_bytes()).hexdigest()
    assert hashes["first/18.2.0"] != hashes["recipient/18.2.0"]
    return hashes


def trial(work, state, project, shared):
    os.environ["DEPLOOM_MCP_STATE_DIR"] = str(state / "planner")
    for name in ("OSV_DIR", "RECORDS_DIR", "PUBLIC_NAMES"):
        os.environ.pop("DEPLOOM_MCP_" + name, None)
    bodies = []
    def counted(url, limit, etag=None):
        data, tag = public_cache.get(url, limit, etag)
        bodies.append(len(data) if data is not None else 0)
        return data, tag

    start = perf_counter()
    if shared:
        public_cache.refresh(state / "osv", counted)
        shared_records.refresh(state / "records", counted)
        os.environ["DEPLOOM_MCP_OSV_DIR"] = str(state / "osv")
        evidence = shared_records.lookup(state / "records", "react-dom", "18.2.0", "18.3.1")
        assert evidence["status"] == "found" and evidence["authority"] == "ADVISORY_ONLY"
    refreshed = perf_counter()
    targets = {"react": "18.3.1", "react-dom": "18.3.1"}
    plan = get_upgrade_plan(project_path=str(work / project / "18.2.0"), registry="https://registry.npmjs.org",
                            objective="explicit-version-targets", exact_targets=targets,
                            mutable_packages=list(targets), deadline_seconds=40, use_system_proxy=True)
    planned = perf_counter()
    if not plan.get("ok"):
        raise ValueError(str(plan.get("error", {}).get("code", "missing plan")))
    # A transferred observation has no authority over this project's independently installed target.
    target = work / project / "18.3.1"
    npm(["ci", "--offline"], target, work / "npm")
    subprocess.run(["node", "-e", "const a=require('node:assert/strict'),r=require('react'),d=require('react-dom/server');"
                    "a.equal(r.version,'18.3.1');a.equal(require('react-dom/package.json').version,r.version);"
                    "a.equal(d.renderToStaticMarkup(r.createElement('p',null,'checked')),'<p>checked</p>')"],
                   cwd=target, check=True, timeout=20)
    checked = perf_counter()
    shutil.rmtree(target / "node_modules")
    return dict(cacheRequests=len(bodies), cacheBodyBytes=sum(bodies), refreshSeconds=round(refreshed-start, 3),
                toPlanSeconds=round(planned-start, 3), toCheckedSeconds=round(checked-start, 3),
                planStatus=plan.get("status"), targetPolicy=plan.get("summary", {}).get("exactTargetPolicy"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("--rounds", type=int, default=4)
    args = parser.parse_args()
    work = args.work.resolve()
    if work.exists() or args.rounds < 1:
        parser.error("Specify a fresh directory and a positive round count")
    work.mkdir(parents=True)
    for name in ("user.npmrc", "global.npmrc"):
        (work / name).touch()
    hashes = fixtures(work)
    rows = []
    for index in range(args.rounds):
        for shared in ((False, True) if index % 2 == 0 else (True, False)):
            state = work / f"r{index}-{int(shared)}"
            for phase, project in (("cold", "first"), ("warm", "first"), ("transfer", "recipient")):
                row = dict(round=index + 1, shared=shared, phase=phase, **trial(work, state, project, shared))
                rows.append(row)
                print(json.dumps(row), flush=True)
                (work / "results.json").write_text(json.dumps({"lockSha256": hashes, "rows": rows}, indent=2))
    for phase in ("cold", "warm", "transfer"):
        for shared in (False, True):
            times = [r["toCheckedSeconds"] for r in rows if (r["phase"], r["shared"]) == (phase, shared)]
            print(phase, shared, "min/median/max checked seconds:", min(times), median(times), max(times))


if __name__ == "__main__":
    main()
