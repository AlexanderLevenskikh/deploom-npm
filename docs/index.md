# DepLoom public data

The [OSV pointer](v1/osv.json) identifies the versioned npm advisory database. Its manifest names the compressed SQLite file and records the hash, schema version, row count and source timestamp. Both files are available in the [immutable data release](https://github.com/levencode-labs/deploom-npm/releases/tag/osv-1795187909-a9143352522e7f89).

The [history](v1/history.json) and [recipes](v1/knowledge.json) are public, reviewed data sets. Both start empty. Clients can request the same files regardless of project dependencies.
