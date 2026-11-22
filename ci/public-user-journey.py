"""Exercise the public installer and real stdio server as an anonymous npm user."""
import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REGISTRY = "https://registry.npmjs.org/"
PACKAGES = ("react", "react-dom")
TARGET = "18.3.1"
TEST = """const assert = require('node:assert/strict');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
assert.equal(renderToStaticMarkup(React.createElement('h1', null, 'Hello DepLoom')), '<h1>Hello DepLoom</h1>');
console.log('SSR passed with React', React.version);
"""


def npm(project, *args, capture=False):
    exe = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    return subprocess.run([exe, *args], cwd=project, check=True, timeout=300,
                          stdout=subprocess.PIPE if capture else None, text=True).stdout


async def from_server(project, home):
    import tomllib
    from mcp import ClientSession, StdioServerParameters, stdio_client

    entry = tomllib.loads((home / ".codex/config.toml").read_text())["mcp_servers"]["deploom"]
    assert (home / ".agents/skills/deploom-upgrade/SKILL.md").is_file()
    params = StdioServerParameters(command=entry["command"], args=entry["args"], env=dict(os.environ), cwd=str(project))
    async with asyncio.timeout(180), stdio_client(params) as streams, ClientSession(*streams) as client:
        await client.initialize()

        async def call(name, arguments):
            result = await client.call_tool(name, arguments)
            assert not result.is_error, result.content
            return result.structured_content or json.loads(result.content[0].text)

        async with asyncio.timeout(75):
            while True:
                row = await call("get_shared_migration_evidence",
                                 dict(package="react", from_version="18.2.0", to_version=TARGET))
                if row["snapshotSource"] == "verified-pages":
                    break
                await asyncio.sleep(1)
        assert any(x["check"] == "install" and x["outcome"] == "passed" for x in row["observations"])
        print("Public signed evidence verified automatically", flush=True)
        result = await call("get_upgrade_plan", dict(project_path=str(project), registry=REGISTRY.rstrip("/"),
                            objective="explicit-version-targets", exact_targets=dict.fromkeys(PACKAGES, TARGET),
                            mutable_packages=list(PACKAGES), deadline_seconds=75, use_system_proxy=True))
        assert result["ok"], result.get("error")
        policy = result["summary"]["exactTargetPolicy"]
        assert policy["allRequestedTargetsProposed"]
        pins = {r["package"]: r["publishedTarget"] for r in policy["publishedAssignments"] if r["rowStatus"] == "PROPOSED"}
        assert pins == dict.fromkeys(PACKAGES, TARGET), pins
        return pins


def upgrade(project, home):
    pins = asyncio.run(from_server(project, home))
    npm(project, "install", "--package-lock-only", "--strict-peer-deps", "--save-exact",
        *[name + "@" + version for name, version in pins.items()])
    npm(project, "ls", "--all", "--package-lock-only")
    assert json.loads((project / "package.json").read_bytes())["dependencies"] == pins
    locked = json.loads((project / "package-lock.json").read_bytes())["packages"]
    assert all(locked["node_modules/" + name]["version"] == version for name, version in pins.items())
    npm(project, "ci", "--strict-peer-deps")
    tree = json.loads(npm(project, "ls", "--json", "--depth=0", capture=True))["dependencies"]
    assert {name: dep["version"] for name, dep in tree.items()} == pins
    npm(project, "test")
    print(platform.system(), platform.machine(), "PASS", pins, flush=True)


def install(root):
    home, project = root / "home", root / "demo"
    for directory in (home, project, home / "local", home / "roaming", home / "temp"):
        directory.mkdir()
    allowed = {"PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "PATHEXT", "COMSPEC", "PROCESSOR_ARCHITECTURE",
               "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "LANG", "LC_ALL", "PROGRAMFILES"}
    env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
    env.update(HOME=str(home), USERPROFILE=str(home), LOCALAPPDATA=str(home / "local"), APPDATA=str(home / "roaming"),
               CODEX_HOME=str(home / ".codex"), XDG_DATA_HOME=str(home / "local"), TEMP=str(home / "temp"),
               TMP=str(home / "temp"), TMPDIR=str(home / "temp"), NPM_CONFIG_REGISTRY=REGISTRY,
               NPM_CONFIG_CACHE=str(home / "npm-cache"), NPM_CONFIG_USERCONFIG=str(home / ".npmrc"),
               NPM_CONFIG_GLOBALCONFIG=str(home / "global.npmrc"), NPM_CONFIG_AUDIT="false", NPM_CONFIG_FUND="false",
               PYTHONIOENCODING="utf-8")
    os.environ.clear()
    os.environ.update(env)
    manifest = dict(name="deploom-public-demo", version="1.0.0", private=True,
                    scripts={"test": "node test.cjs"}, dependencies=dict.fromkeys(PACKAGES, "18.2.0"))
    (project / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
    (project / "test.cjs").write_text(TEST, encoding="utf-8")
    npm(project, "install", "--strict-peer-deps")
    npm(project, "test")
    npm(project, "exec", "--yes", "--package=@levencode/deploom", "--", "deploom", "setup", "codex")
    base = home / "local/DepLoom/public"
    version = json.loads((base / "clients/codex/active.json").read_text())["version"]
    print("Installed publicly distributed version", version, flush=True)
    runtime = base / "versions" / version / ("python.exe" if os.name == "nt" else "bin/python3.13")
    subprocess.run([str(runtime), "-I", "-B", str(Path(__file__).resolve()), str(project), str(home)], check=True)


if __name__ == "__main__":
    if len(sys.argv) == 3:
        upgrade(*(Path(arg) for arg in sys.argv[1:]))
    else:
        with tempfile.TemporaryDirectory() as directory:
            install(Path(directory))
