# DepLoom for npm

This repository builds the Windows x64 distribution of the [DepLoom MCP server and Skill](https://github.com/levencode-labs/deploom-mcp) and the public npm advisory index. The package is in development.

## Public data

Run `python cache/build_osv.py build/osv` with Python 3.12 or newer to create an index from the public npm ecosystem export. The output includes the compressed SQLite database and its versioned manifest. Run `python -m unittest discover -s cache` for the synthetic export test.

## License

The installer and first-party data tooling use the [Apache License 2.0](LICENSE). The runtime components and advisory data retain their respective licenses.
