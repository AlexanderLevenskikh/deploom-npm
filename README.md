# DepLoom for npm

This repository builds the Windows x64 distribution of the [DepLoom MCP server and Skill](https://github.com/levencode-labs/deploom-mcp) and the public npm advisory index. The package is in development.

## Windows installer

The public package name is `@levencode/deploom`. The first release targets Windows x64 with Node 22 or later. The archive includes CPython, the MCP server, its pinned Core, the upgrade Skill, and third-party notices. Setup copies the runtime to a versioned directory under `%LOCALAPPDATA%\DepLoom\public`. The installed MCP keeps working after npm clears its download cache.

To test a candidate offline, run the following from the directory containing its tarball. Replace `codex` with `opencode` or `claude` for those clients.

```powershell
npm.cmd install --offline --prefix .\test-install .\levencode-deploom-0.2.21-next.1.tgz
.\test-install\node_modules\.bin\deploom.cmd setup codex
```

Restart the client to discover the Skill. To switch back to the previous version retained for that client, run `deploom rollback codex` from an installed CLI. To refresh the shared public npm advisory snapshot explicitly, run `deploom cache refresh`. The client fetches fixed public URLs, verifies the snapshot locally and retains the previous working data if refresh fails. Refresh the snapshot again before its seven-day freshness window expires. An expired snapshot provides unknown security evidence.

The Windows CI workflow builds a development wheel from the pinned public sources, verifies the CPython archive and every wheel against the lock file, and checks the actual npm tarball. Production publication requires a released MCP wheel. To run the installation test on Windows with the three clients on PATH, use `ci/test-install.ps1 -Tarball <archive> -Work <new-directory>`.

## Public data

Run `python cache/build_osv.py build/osv` with Python 3.12 or newer to create an index from the public npm ecosystem export. The output includes the compressed SQLite database and its versioned manifest. Run `python -m unittest discover -s cache` for the synthetic export test.

## Sharing an observation

Reproduce a migration in a public fixture under `fixtures/<name>/check.cjs`. The fixture should install exact public versions and run the stated check. Once it passes on GitHub, use its immutable commit URL as `source` in a pull request against `docs/v1/history.json` or `docs/v1/knowledge.json`. The record identifies the package, old and new version, and the observed check or named recipe. Reviewers can rerun the fixture before merging. Installed clients only read the snapshots. Project lockfiles, dependency inventories and local results stay on the developer's machine.

Use `get_shared_migration_evidence` to look up an exact transition after refreshing the cache. A passing result on the example is advisory. Run the checks that matter for the receiving project.

## License

The installer and first-party data tooling use the [Apache License 2.0](LICENSE). The runtime components and advisory data retain their respective licenses.
