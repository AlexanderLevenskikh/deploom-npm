'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { buildRuntime, target, sha } = require('../bin/posix-runtime.cjs');

const root = path.resolve(__dirname, '..');
const out = path.resolve(process.argv[2]);
fs.mkdirSync(out);
const stage = fs.mkdtempSync(path.join(out, 'stage-'));
try {
  const runtime = path.join(stage, 'runtime');
  const pkg = path.join(stage, 'package');
  fs.mkdirSync(runtime);
  fs.mkdirSync(pkg);
  buildRuntime(runtime, root, stage);
  for (const item of ['bin', 'vendor', 'README.md', 'LICENSE']) {
    fs.cpSync(path.join(root, item), path.join(pkg, item), { recursive: true });
  }
  const meta = JSON.parse(fs.readFileSync(path.join(root, 'package.json')));
  meta.os = [process.platform];
  meta.cpu = [process.arch];
  fs.writeFileSync(path.join(pkg, 'package.json'), JSON.stringify(meta, null, 2) + '\n');
  const archive = path.join(pkg, 'portable-runtime.tar.gz');
  execFileSync('tar', ['-czf', archive, '-C', runtime, '.'], { stdio: 'inherit' });
  fs.writeFileSync(path.join(pkg, 'posix-offline.json'), JSON.stringify({ version: meta.version, target, sha256: sha(archive) }) + '\n');
  const notices = path.join(pkg, 'THIRD_PARTY_NOTICES');
  fs.mkdirSync(notices);
  fs.copyFileSync(path.join(pkg, 'bin/Z3-LICENSE.txt'), path.join(notices, 'Z3-LICENSE.txt'));
  fs.writeFileSync(path.join(notices, 'README.txt'), 'The embedded CPython distribution and installed Python libraries retain their licenses inside portable-runtime.tar.gz.\n');
  execFileSync('npm', ['pack', '--offline', '--quiet', '--pack-destination', out], { cwd: pkg, stdio: 'inherit' });
  fs.renameSync(path.join(out, 'levencode-deploom-' + meta.version + '.tgz'), path.join(out, 'deploom-' + target + '-' + meta.version + '.tgz'));
} finally { fs.rmSync(stage, { recursive: true, force: true }); }
