'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { pythonBin } = require('../bin/launch.cjs');

test('offline diagnostic forwards arguments to the installed version and preserves its error status', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'deploom-diagnosis-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const data = path.join(root, 'fresh-data-home');
  const env = { ...process.env, XDG_DATA_HOME: data, LOCALAPPDATA: data };
  const cli = path.join(__dirname, '../bin/deploom.cjs');
  const args = ['diagnose-coverage', 'saved run/result.json', '--snapshot-dir', 'historical snapshot',
    '--inventory', 'saved audit/canonical-yarn-inventory.json', '--focus', '@example/test'];
  const missing = spawnSync(process.execPath, [cli, ...args], { env, encoding: 'utf8' });
  assert.equal(missing.status, 1);
  assert.match(missing.stderr, /runtime is missing/);
  assert.equal(fs.existsSync(data), false);

  const version = require('../package.json').version;
  const python = pythonBin(path.join(data, 'DepLoom/public/versions', version));
  fs.mkdirSync(path.dirname(python), { recursive: true });
  fs.writeFileSync(python, '');
  const capture = path.join(root, 'capture.cjs');
  fs.writeFileSync(capture, `
    require('node:child_process').execFileSync = (command, args, options) => {
      process.stdout.write(JSON.stringify({ command, args, stdio: options.stdio }));
      throw Object.assign(new Error('diagnostic exit'), { status: 2 });
    };
  `);
  const result = spawnSync(process.execPath, ['--require', capture, cli, ...args], { env, encoding: 'utf8' });
  assert.equal(result.status, 2, result.stderr);
  assert.equal(result.stderr, '');
  assert.deepEqual(JSON.parse(result.stdout), { command: python, stdio: 'inherit',
    args: ['-I', '-B', '-m', 'deploom_mcp.coverage_diagnosis', ...args.slice(1)] });
});
