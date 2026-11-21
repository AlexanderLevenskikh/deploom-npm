'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');

const digestPattern = /^[0-9a-f]{64}$/;
const day = 86400;

async function cacheStatus(root, now = Date.now() / 1000) {
  let manifest;
  try {
    manifest = JSON.parse(await fs.promises.readFile(path.join(root, 'active.json'), 'utf8'));
  } catch (error) {
    if (error.code === 'ENOENT') return { status: 'missing' };
    return { status: 'invalid', reason: 'manifest-unreadable' };
  }
  if (!manifest || manifest.schema !== 1 || manifest.ecosystem !== 'npm' ||
      typeof manifest.sha256 !== 'string' || !digestPattern.test(manifest.sha256) ||
      typeof manifest.databaseSha256 !== 'string' || !digestPattern.test(manifest.databaseSha256) ||
      !Number.isSafeInteger(manifest.published) || manifest.published < 0 || manifest.published > now + 300 ||
      manifest.expires !== manifest.published + 7 * day ||
      manifest.tag !== `osv-${manifest.published}-${manifest.sha256.slice(0, 16)}` ||
      !Number.isSafeInteger(manifest.unpacked) || manifest.unpacked <= 0 || manifest.unpacked > 256_000_000) {
    return { status: 'invalid', reason: 'manifest-fields' };
  }
  const db = path.join(root, manifest.sha256 + '.sqlite');
  try {
    const stat = await fs.promises.stat(db);
    if (!stat.isFile() || stat.size !== manifest.unpacked) return { status: 'invalid', reason: 'database-size' };
    const hash = createHash('sha256');
    for await (const chunk of fs.createReadStream(db, { end: manifest.unpacked })) hash.update(chunk);
    if (hash.digest('hex') !== manifest.databaseSha256) return { status: 'invalid', reason: 'database-digest' };
  } catch {
    return { status: 'invalid', reason: 'database-unreadable' };
  }
  const remaining = manifest.expires - now;
  const status = remaining <= 0 ? 'expired' : remaining <= 2 * day ? 'expiring' : 'fresh';
  return { status, tag: manifest.tag, publishedAt: new Date(manifest.published * 1000).toISOString(),
    expiresAt: new Date(manifest.expires * 1000).toISOString(), sha256: manifest.sha256 };
}

module.exports = { cacheStatus };
