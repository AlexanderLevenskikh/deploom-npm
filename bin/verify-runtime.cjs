'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

function verifyRuntime(root, manifest) {
  if (manifest.schema !== 1 || !Array.isArray(manifest.files) || !manifest.files.length) {
    throw Error('Invalid runtime manifest');
  }
  const expected = new Map();
  for (const { name, sha256 } of manifest.files) {
    if (typeof name !== 'string' || name.includes('\\') || name.includes(':') ||
        name.split('/').some(part => !part || part === '.' || part === '..') ||
        !/^[a-f0-9]{64}$/.test(sha256) || expected.has(name)) throw Error('Invalid runtime file record');
    expected.set(name, sha256);
  }
  for (const required of ['python.exe', 'LICENSE.txt', 'Lib/site-packages/deploom_mcp/__init__.py',
    'Lib/site-packages/deploom_mcp/resources/skills/deploom-upgrade/SKILL.md']) {
    if (!expected.has(required)) throw Error('Missing runtime component: ' + required);
  }
  function visit(dir, prefix) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const name = prefix + entry.name;
      const file = path.join(dir, entry.name);
      if (entry.isDirectory()) visit(file, name + '/');
      else {
        if (!entry.isFile() || !expected.has(name)) throw Error('Unexpected runtime entry: ' + name);
        const hash = crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
        if (hash !== expected.get(name)) throw Error('Runtime digest mismatch: ' + name);
        expected.delete(name);
      }
    }
  }
  visit(root, '');
  if (expected.size) throw Error('Missing runtime file: ' + expected.keys().next().value);
}
module.exports = { verifyRuntime };
if (require.main === module) {
  const pkg = path.join(__dirname, '..');
  verifyRuntime(path.join(pkg, 'runtime'), require('../runtime-manifest.json'));
  if (!fs.readdirSync(path.join(pkg, 'THIRD_PARTY_NOTICES')).length) throw Error('Missing third-party notices');
}
