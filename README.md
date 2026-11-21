<div align="center">

<img src="https://raw.githubusercontent.com/levencode-labs/deploom-npm/main/assets/social-preview.png" width="768" alt="DepLoom npm installer" />

# Deploom npm

**Install the DepLoom MCP server and upgrade Skill on Windows, Linux, and macOS.**

[Windows setup](#windows-installer) · [Linux and macOS](#linux-and-macos) · [Offline setup](#offline-setup) · [Public data](#public-data) · [Releases](https://github.com/levencode-labs/deploom-npm/releases?q=npm-v) · [Levencode Labs](https://github.com/levencode-labs)

</div>

Use one package with Codex, Claude Code, or OpenCode. It includes the [MCP server and Skill](https://github.com/levencode-labs/deploom-mcp), the pinned [planning engine](https://github.com/levencode-labs/deploom-core), and an embedded Python runtime. The project also publishes a shared index of npm security advisories.

## Windows installer

**Requirements**

Windows x64, Node.js 22 or later with npm, and a supported client. Setup copies the runtime to a versioned directory under `%LOCALAPPDATA%\DepLoom\public`. The installed MCP keeps working after npm clears its download cache.

To install the pinned prerelease from npm, run this command in PowerShell. The example configures Codex. Use `claude` for Claude Code or `opencode` for OpenCode.

```powershell
npm.cmd exec --yes --package=@levencode/deploom@0.2.21-next.2 -- deploom setup codex
```

## Offline setup

Copy the `.tgz` from the [Windows prerelease](https://github.com/levencode-labs/deploom-npm/releases/tag/npm-v0.2.21-next.2) to the target machine. Open PowerShell in the directory containing the archive. The same command works with an empty npm cache.

```powershell
npm.cmd exec --offline --yes --package=./levencode-deploom-0.2.21-next.2.tgz -- deploom setup codex
```

Restart the client after setup to load the server and discover the Skill.

## Linux and macOS

Use Node.js 22 or newer with npm. The Linux builds target glibc on x64 and ARM64. The macOS build targets Apple Silicon. The native CI runs on Ubuntu 24.04 and macOS 15.

For an online installation, run the following from your project. First setup downloads a private CPython interpreter from GitHub and hash-checked packages from PyPI and the DepLoom MCP release. The installed server runs locally.

```sh
npm exec --yes --package=@levencode/deploom@0.2.21-next.4 -- deploom setup codex
```

For an offline installation, download the archive matching the destination machine from the [prerelease assets](https://github.com/levencode-labs/deploom-npm/releases/tag/npm-v0.2.21-next.4). The available archive prefixes are `deploom-linux-x64`, `deploom-linux-arm64`, and `deploom-darwin-arm64`. For example, on Apple Silicon run the following in the directory containing the file.

```sh
npm exec --offline --yes --package=./deploom-darwin-arm64-0.2.21-next.4.tgz -- deploom setup codex
```

Use `claude` or `opencode` in place of `codex` to register another client. Keep running Node.js on its native architecture. Intel macOS, Alpine/musl and Windows ARM64 are outside this release's supported matrix.

## Updates and rollback

To switch back to the previous version retained for that client, run `deploom rollback codex` from an installed CLI. To refresh the shared public npm advisory snapshot explicitly, run `deploom cache refresh`. The client fetches fixed public URLs, verifies the snapshot locally and retains the previous working data if refresh fails. Refresh the snapshot again before its seven-day freshness window expires. An expired snapshot provides unknown security evidence.

## Release checks

The Windows CI workflow builds a development wheel from the pinned public sources, verifies the CPython archive and every wheel against the lock file, and checks the actual npm tarball. The release workflow pins the official MCP wheel in `ci/mcp-release.json`, tests the packed bytes on Windows, and publishes the same archive to the npm `next` tag using GitHub OIDC. A second Windows runner checks the npm download and the exact-version install before the GitHub release publishes `upstream.json` and the tarball for downstream import. To run the installation test on Windows with the three clients on PATH, use `ci/test-install.ps1 -Tarball <archive> -Work <new-directory>`.

## Public data

Run `python cache/build_osv.py build/osv` with Python 3.12 or newer to create an index from the public npm ecosystem export. The output includes the compressed SQLite database and its versioned manifest. Run `python -m unittest discover -s cache` for the synthetic export test.

## Sharing an observation

Reproduce a migration in a public fixture under `fixtures/<name>/check.cjs`. The fixture should install exact public versions and run the stated check. Once it passes on GitHub, use its immutable commit URL as `source` in a pull request against `docs/v1/history.json` or `docs/v1/knowledge.json`. The record identifies the package, old and new version, and the observed check or named recipe. Reviewers can rerun the fixture before merging. Installed clients only read the snapshots. Project lockfiles, dependency inventories and local results stay on the developer's machine.

Use `get_shared_migration_evidence` to look up an exact transition after refreshing the cache. A passing result on the example is advisory. Run the checks that matter for the receiving project.

## License

The installer and first-party data tooling use the [Apache License 2.0](LICENSE). Runtime components retain their upstream licenses. Installation and redistribution of the Windows binaries are offered subject to the [CPython Windows binary conditions](https://github.com/python/cpython/blob/3.13/PC/crtlicense.txt). Distributors and external users must agree to those terms for the Microsoft code delivered with the Python interpreter. The package contains the complete original terms in `runtime/LICENSE.txt` and `THIRD_PARTY_NOTICES/CPython/LICENSE.txt`.

The two Visual C++ runtime files included with CPython are distributed unchanged as part of that interpreter. The Z3 binaries are built from the pinned Z3 source with MinGW-w64. Their source identity, compiler notices and GCC Runtime Library Exception are included under `THIRD_PARTY_NOTICES/z3-solver/`. The Windows integration includes the pywin32 components used by the MCP. The optional Pythonwin GUI and Exchange MAPI extensions are omitted.
