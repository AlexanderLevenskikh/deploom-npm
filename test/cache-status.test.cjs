'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { createHash } = require('node:crypto');
const { spawnSync } = require('node:child_process');
const { cacheStatus } = require('../bin/cache-status.cjs');

function edition(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'deploom-status-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const bytes = Buffer.from('verified fixture bytes');
  const sha256 = 'a'.repeat(64);
  const published = Math.floor(Date.now() / 1000);
  const manifest = { schema: 1, ecosystem: 'npm', published, expires: published + 7 * 86400,
    unpacked: bytes.length, sha256, databaseSha256: createHash('sha256').update(bytes).digest('hex'),
    tag: `osv-${published}-${sha256.slice(0, 16)}` };
  const active = path.join(root, 'active.json');
  fs.writeFileSync(active, JSON.stringify(manifest));
  const db = path.join(root, sha256 + '.sqlite');
  fs.writeFileSync(db, bytes);
  return { root, manifest, active, db };
}

test('local status uses the source timestamp and exact seven-day expiry', async t => {
  const { root, manifest } = edition(t);
  const fresh = await cacheStatus(root, manifest.published);
  assert.equal(fresh.status, 'fresh');
  assert.equal(fresh.sha256, manifest.sha256);
  assert.equal(fresh.expiresAt, new Date(manifest.expires * 1000).toISOString());
  assert.equal((await cacheStatus(root, manifest.expires - 2 * 86400)).status, 'expiring');
  assert.equal((await cacheStatus(root, manifest.expires)).status, 'expired');
  assert.equal((await cacheStatus(root, manifest.published - 301)).status, 'invalid');
});

test('missing, partial and same-size corrupt editions give no freshness claim', async t => {
  const { root, manifest, active, db } = edition(t);
  fs.writeFileSync(db, Buffer.alloc(manifest.unpacked));
  assert.equal((await cacheStatus(root)).reason, 'database-digest');
  fs.truncateSync(db, 1);
  assert.equal((await cacheStatus(root)).reason, 'database-size');
  fs.unlinkSync(db);
  assert.equal((await cacheStatus(root)).reason, 'database-unreadable');
  fs.writeFileSync(active, '{');
  assert.equal((await cacheStatus(root)).reason, 'manifest-unreadable');
  fs.unlinkSync(active);
  assert.equal((await cacheStatus(root)).status, 'missing');
});

test('CLI checks the configured directory before setup and leaves the data home untouched', t => {
  const { root, manifest } = edition(t);
  const dataHome = path.join(root, 'unused-data-home');
  const env = { ...process.env, XDG_DATA_HOME: dataHome, LOCALAPPDATA: dataHome, DEPLOOM_MCP_OSV_DIR: root };
  const run = () => spawnSync(process.execPath, [path.join(__dirname, '../bin/deploom.cjs'), 'cache', 'status'],
    { env, encoding: 'utf8' });
  const found = run();
  assert.equal(found.status, 0, found.stderr);
  assert.equal(JSON.parse(found.stdout).tag, manifest.tag);
  delete env.DEPLOOM_MCP_OSV_DIR;
  const missing = run();
  assert.equal(missing.status, 1, missing.stderr);
  assert.equal(JSON.parse(missing.stdout).status, 'missing');
  assert.equal(fs.existsSync(dataHome), false);
});
