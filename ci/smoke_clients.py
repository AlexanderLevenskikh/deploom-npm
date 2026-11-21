"""Check installed client entries against a synthetic npm project, without network."""
import argparse
import asyncio
import json
import os
import tempfile
import tomllib
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, stdio_client


async def check(client, command, skill, fixture, profile):
    params = StdioServerParameters(command=command[0], args=command[1:], cwd=str(fixture),
                                  env={**os.environ, "USERPROFILE": str(profile),
                                       "LOCALAPPDATA": str(profile / "local"),
                                       "DEPLOOM_MCP_STATE_DIR": str(profile / "state")})
    async with asyncio.timeout(45), stdio_client(params) as (rx, tx), ClientSession(rx, tx) as session:
        init = await session.initialize()
        contract = json.loads((skill / "contract.json").read_bytes())
        if not (skill / "SKILL.md").is_file() or not contract["bundleSha256"]:
            raise ValueError(f"{client}: installed Skill missing")
        listed = await session.list_tools()
        names = {tool.name for tool in listed.tools}
        if not {"get_upgrade_plan", "get_project_capabilities"}.issubset(names):
            raise RuntimeError(f"{client}: expected tools missing")
        result = await session.call_tool("get_project_capabilities", {"project_path": str(fixture)})
        payload = result.structured_content or json.loads(result.content[0].text)
        if result.is_error or not payload.get("ok") or not payload.get("routes"):
            raise RuntimeError(f"{client}: no usable project route: {payload}")
        print(json.dumps(dict(client=client, protocol=init.protocol_version, tools=len(names),
                              routes=[r["tool"] for r in payload["routes"]],
                              skill=contract["contractVersion"])))


async def smoke(profile, selected):
    clients = []
    if selected in (None, "claude"):
        claude = json.loads((profile / ".claude/.claude.json").read_bytes())["mcpServers"]["deploom"]
        clients.append(("claude", [claude["command"], *claude["args"]], ".claude/skills"))
    if selected in (None, "codex"):
        codex = tomllib.loads((profile / ".codex/config.toml").read_text())["mcp_servers"]["deploom"]
        clients.append(("codex", [codex["command"], *codex["args"]], ".agents/skills"))
    if selected in (None, "opencode"):
        opencode = json.loads((profile / ".config/opencode/opencode.jsonc").read_bytes())["mcp"]
        clients.append(("opencode", opencode.get("servers", opencode)["deploom"]["command"], ".config/opencode/skills"))
    with tempfile.TemporaryDirectory(dir=profile) as directory:
        fixture = Path(directory)
        project = {"name": "offline-example", "version": "1.0.0", "dependencies": {"example": "1.0.0"}}
        (fixture / "package.json").write_text(json.dumps(project))
        (fixture / "package-lock.json").write_text(json.dumps({
            "name": project["name"], "version": project["version"], "lockfileVersion": 3,
            "packages": {"": project, "node_modules/example": {"version": "1.0.0"}}}))
        for client, cmd, location in clients:
            await check(client, cmd, profile / location / "deploom-upgrade", fixture, profile)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path, help="Home directory of the isolated test user")
    parser.add_argument("--client", choices=("claude", "codex", "opencode"))
    args = parser.parse_args()
    asyncio.run(smoke(args.profile.resolve(), args.client))
