// Public example: update React and its DOM renderer, then check the installed tree.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { spawnSync } = require('node:child_process');
const assert = require('node:assert/strict');

const project = fs.mkdtempSync(path.join(os.tmpdir(), 'deploom-example-'));
function manifest(react, renderer) {
  fs.writeFileSync(path.join(project, 'package.json'), JSON.stringify({
    name: 'public-renderer-example', version: '1.0.0', private: true,
    dependencies: { react, 'react-dom': renderer },
  }));
}
function npm(args) {
  const windows = process.platform === 'win32';
  const cmd = windows ? (process.env.ComSpec || 'cmd.exe') : 'npm';
  const argv = windows ? ['/d', '/c', 'npm.cmd', ...args] : args;
  const result = spawnSync(cmd, argv, { cwd: project, encoding: 'utf8', windowsHide: true, timeout: 120000 });
  if (result.error) throw result.error;
  return result;
}
function install() {
  return npm(['install', '--registry=https://registry.npmjs.org/', '--ignore-scripts', '--strict-peer-deps', '--no-audit', '--no-fund']);
}
try {
  manifest('18.2.0', '18.2.0');
  let result = install();
  assert.equal(result.status, 0, result.stderr);
  manifest('18.2.0', '18.3.1');
  result = install();
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /ERESOLVE/);
  manifest('18.3.1', '18.3.1');
  result = install();
  assert.equal(result.status, 0, result.stderr);
  const tree = npm(['ls', '--json', '--depth=0']);
  assert.equal(tree.status, 0, tree.stderr);
  const deps = JSON.parse(tree.stdout).dependencies;
  assert.equal(deps.react.version, '18.3.1');
  assert.equal(deps['react-dom'].version, '18.3.1');
  console.log('Verified the 18.2.0 baseline, rejected mismatched peers, and installed both 18.3.1 targets.');
} finally {
  fs.rmSync(project, { recursive: true, force: true });
}
