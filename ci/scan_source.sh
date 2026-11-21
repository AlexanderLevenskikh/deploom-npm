#!/bin/sh
# Run Semgrep locally against this checkout and the exact public sources in the release pin.
set -eu
pin=$(realpath "$1")
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir "$work/source" "$work/source/installer"
git archive HEAD | tar -x -C "$work/source/installer"

python3 - "$pin" "$work" <<'PY'
import json, re, subprocess, sys
from pathlib import Path
pin = json.loads(Path(sys.argv[1]).read_bytes())
mcp = pin.get("mcp", pin)
revisions = {"deploom-mcp": mcp["commit"], "deploom-core": mcp["coreRevision"]}
if "mcp" in pin:
    revisions["deploom-npm"] = pin["commit"]
for repo, revision in revisions.items():
    if not re.fullmatch("[a-f0-9]{40}", revision):
        raise ValueError("Expected exact upstream revision for " + repo)
    dest = Path(sys.argv[2]) / "source" / repo
    subprocess.run(["git", "init", "-q", str(dest)], check=True)
    git = ["git", "-C", str(dest)]
    subprocess.run([*git, "fetch", "--quiet", "--depth=1",
                    "https://github.com/levencode-labs/" + repo + ".git", revision], check=True)
    assert subprocess.check_output([*git, "rev-parse", "FETCH_HEAD"], text=True).strip() == revision
    subprocess.run([*git, "checkout", "-q", "--detach", revision], check=True)
PY
rules="$work/rules"
revision=a5ad1714f00c9f7fde980cab0ea1d6dc6d414fd2
git init -q "$rules"
git -C "$rules" fetch -q --depth=1 https://github.com/semgrep/semgrep-rules.git "$revision"
git -C "$rules" checkout -q --detach "$revision"
cd "$work/source"
semgrep scan --metrics=off --disable-version-check --strict --error --severity ERROR \
  --config "$rules/python/lang/security" --config "$rules/javascript/lang/security" \
  --config "$rules/typescript/lang/security" --config "$rules/bash" \
  --config "$rules/yaml/github-actions" --config "$rules/yaml/gitlab" \
  --config "$rules/dockerfile/security" --no-git-ignore --exclude '.git' .
