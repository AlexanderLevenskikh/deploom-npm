# DepLoom for npm

This repository builds the Windows x64 distribution of the [DepLoom MCP server and Skill](https://github.com/levencode-labs/deploom-mcp) and the public npm advisory index.

## Windows installer

The public package name is `@levencode/deploom`. The first release targets Windows x64 with Node 22 or later. The archive includes the official PSF embeddable CPython distribution, the MCP server, its pinned Core, the upgrade Skill, and third-party notices. Setup copies the runtime to a versioned directory under `%LOCALAPPDATA%\DepLoom\public`. The installed MCP keeps working after npm clears its download cache.

For the first prerelease, use an exact version on Windows after it appears in the public registry. Choose the client you already have installed.

```powershell
npm.cmd exec --yes --package=@levencode/deploom@0.2.21-next.1 -- deploom setup codex
```

To test a candidate offline, run the following from the directory containing its tarball. Replace `codex` with `opencode` or `claude` for those clients.

```powershell
npm.cmd install --offline --prefix .\test-install .\levencode-deploom-0.2.21-next.1.tgz
.\test-install\node_modules\.bin\deploom.cmd setup codex
```

Restart the client to discover the Skill. To switch back to the previous version retained for that client, run `deploom rollback codex` from an installed CLI. To refresh the shared public npm advisory snapshot explicitly, run `deploom cache refresh`. The client fetches fixed public URLs, verifies the snapshot locally and retains the previous working data if refresh fails. Refresh the snapshot again before its seven-day freshness window expires. An expired snapshot provides unknown security evidence.

The Windows CI workflow builds a development wheel from the pinned public sources, verifies the CPython archive and every wheel against the lock file, and checks the actual npm tarball. The release workflow pins the official MCP wheel in `ci/mcp-release.json`, tests the packed bytes on Windows, and publishes the same archive to the npm `next` tag using GitHub OIDC. A second Windows runner checks the npm download and the exact-version install before the GitHub release publishes `upstream.json` and the tarball for downstream import. To run the installation test on Windows with the three clients on PATH, use `ci/test-install.ps1 -Tarball <archive> -Work <new-directory>`.

## Public data

Run `python cache/build_osv.py build/osv` with Python 3.12 or newer to create an index from the public npm ecosystem export. The output includes the compressed SQLite database and its versioned manifest. Run `python -m unittest discover -s cache` for the synthetic export test.

## Sharing an observation

Reproduce a migration in a public fixture under `fixtures/<name>/check.cjs`. The fixture should install exact public versions and run the stated check. Once it passes on GitHub, use its immutable commit URL as `source` in a pull request against `docs/v1/history.json` or `docs/v1/knowledge.json`. The record identifies the package, old and new version, and the observed check or named recipe. Reviewers can rerun the fixture before merging. Installed clients only read the snapshots. Project lockfiles, dependency inventories and local results stay on the developer's machine.

Use `get_shared_migration_evidence` to look up an exact transition after refreshing the cache. A passing result on the example is advisory. Run the checks that matter for the receiving project.

## License

The installer and first-party data tooling use the [Apache License 2.0](LICENSE). Runtime components retain their upstream licenses. Installation and redistribution of the Windows binaries are offered subject to the [CPython Windows binary conditions](https://github.com/python/cpython/blob/3.13/PC/crtlicense.txt). Distributors and external users must agree to those terms for the Microsoft code delivered with the Python interpreter. The package contains the complete original terms in `runtime/LICENSE.txt` and `THIRD_PARTY_NOTICES/CPython/LICENSE.txt`.

The two Visual C++ runtime files included with CPython are distributed unchanged as part of that interpreter. The Z3 binaries are built from the pinned Z3 source with MinGW-w64. Their source identity, compiler notices and GCC Runtime Library Exception are included under `THIRD_PARTY_NOTICES/z3-solver/`. The Windows integration includes the pywin32 components used by the MCP. The optional Pythonwin GUI and Exchange MAPI extensions are omitted.
