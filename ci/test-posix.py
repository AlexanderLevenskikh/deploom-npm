"""Exercise all three client registrations from an offline archive or a public npm release."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
source = parser.add_mutually_exclusive_group(required=True)
source.add_argument("--registry")
source.add_argument("archive", nargs="?", type=Path)
args = parser.parse_args()
spec = args.registry or str(args.archive.resolve(strict=True))
with tempfile.TemporaryDirectory() as temp:
    profile = Path(temp).resolve()
    env = {**os.environ, "HOME": str(profile), "CODEX_HOME": str(profile / ".codex"),
           "CLAUDE_CONFIG_DIR": str(profile / ".claude"), "OPENCODE_CONFIG_DIR": str(profile / ".config/opencode"),
           "XDG_DATA_HOME": str(profile / "data"), "npm_config_cache": str(profile / "cache"),
           "npm_config_registry": "https://registry.npmjs.org/"}
    if args.archive:
        env.update({"npm_config_offline": "true", "HTTPS_PROXY": "http://127.0.0.1:1", "HTTP_PROXY": "http://127.0.0.1:1",
           "ALL_PROXY": "http://127.0.0.1:1", "NO_PROXY": "127.0.0.1,localhost"})
    for client in ("claude", "codex", "opencode"):
        subprocess.run(["npm", "exec", "--yes", "--package=" + spec, "--",
                        "deploom", "setup", client], cwd=profile, env=env, check=True, timeout=600)
    base = profile / "data/DepLoom/public"
    version = json.loads((base / "clients/codex/active.json").read_bytes())["version"]
    python = base / "versions" / version / "bin/python3.13"
    subprocess.run([str(python), "-I", "-B", str(Path(__file__).with_name("smoke_clients.py").resolve()), str(profile)],
                   cwd=profile, env=env, check=True, timeout=180)
    scripts = Path(__file__).resolve().parent
    subprocess.run(["node", str(scripts / "codex-skill.cjs"), str(profile)], cwd=profile, env=env, check=True, timeout=90)
    subprocess.run(["node", str(scripts / "opencode-skill.cjs")], cwd=profile, env=env, check=True, timeout=90)
    request = {"type": "control_request", "request_id": "check-skill", "request": {"subtype": "initialize"}}
    result = subprocess.run(["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json",
                             "--verbose", "--no-session-persistence"], cwd=profile,
                            env={**env, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "DISABLE_AUTOUPDATER": "1"},
                            input=json.dumps(request) + "\n", capture_output=True, text=True, check=True, timeout=90)
    packets = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    reply = next(p["response"] for p in packets if p["type"] == "control_response"
                 and p["response"].get("request_id") == "check-skill")
    if reply["subtype"] != "success" or "deploom-upgrade" not in {c["name"] for c in reply["response"]["commands"]}:
        raise RuntimeError("Claude Code did not discover the installed Skill")
    print("Claude Code discovered the installed Skill")
    entry = base / "versions" / version / "lib/python3.13/site-packages/deploom_mcp/__init__.py"
    with entry.open("ab") as stream:
        stream.write(b"\n# modified after installation\n")
    retry = subprocess.run(["npm", "exec", "--yes", "--package=" + spec, "--", "deploom", "setup", "codex"],
                           cwd=profile, env=env, capture_output=True, text=True, timeout=120)
    if retry.returncode == 0 or "Installed runtime is incomplete" not in retry.stderr:
        raise RuntimeError("A modified runtime was not detected", retry.stderr)
