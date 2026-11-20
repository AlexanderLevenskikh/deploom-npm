"""Exercise the consumer command with an empty npm cache and no runtime downloads."""
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
