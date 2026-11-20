'use strict';
const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');
const crypto = require('node:crypto');
const { spawn } = require('node:child_process');
const versionPattern = /^\d+\.\d+\.\d+(?:-[a-z0-9]+(?:\.[a-z0-9]+)*)?$/i;

function pythonBin(runtime) {
  return path.join(runtime, process.platform === 'win32' ? 'python.exe' : 'bin/python3.13');
}
function sitePackages(runtime) {
  return path.join(runtime, process.platform === 'win32' ? 'Lib/site-packages' : 'lib/python3.13/site-packages');
}

async function withLock(base, action) {
  const key = crypto.createHash('sha256').update(base.toLowerCase()).digest('hex');
  const server = net.createServer(socket => socket.destroy());
  const timeout = Date.now() + 120_000;
  for (;;) {
    try {
      await new Promise((resolve, reject) => {
        function ready() { server.off('error', failed); resolve(); }
        function failed(error) { server.off('listening', ready); reject(error); }
        server.once('error', failed);
        server.once('listening', ready);
        if (process.platform === 'win32') server.listen('\\\\.\\pipe\\deploom-' + key);
        else {
          // A loopback listener releases the lock on process death, including on macOS.
          server.listen({ host: '127.0.0.1', port: 16384 + parseInt(key.slice(0, 8), 16) % 45000 });
        }
      });
      break;
    } catch (error) {
      if (error.code !== 'EADDRINUSE' || Date.now() >= timeout) throw error;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }
  try { return await action(); } finally { server.close(); }
}

async function launch(profile) {
  const base = path.resolve(profile, '../..');
  await withLock(base, async () => {
    if (fs.existsSync(path.join(profile, 'transaction.json'))) {
      throw Error('DepLoom activation is incomplete. Run deploom setup ' + path.basename(profile) + ' to recover.');
    }
    const { version } = JSON.parse(fs.readFileSync(path.join(profile, 'active.json'), 'utf8'));
    if (typeof version !== 'string' || !versionPattern.test(version)) throw Error('Invalid active version');
    const runtime = path.join(base, 'versions', version);
    const cache = path.join(base, 'cache', 'osv');
    const env = { ...process.env };
    if (!env.DEPLOOM_MCP_OSV_DIR && fs.existsSync(cache)) env.DEPLOOM_MCP_OSV_DIR = cache;
    const records = path.join(base, 'cache', 'records');
    if (!env.DEPLOOM_MCP_RECORDS_DIR && fs.existsSync(records)) env.DEPLOOM_MCP_RECORDS_DIR = records;
    const leases = path.join(base, 'running', version);
    fs.mkdirSync(leases, { recursive: true });
    const starting = path.join(leases, 'starting-' + crypto.randomUUID());
    fs.writeFileSync(starting, '', { flag: 'wx' });
    const child = spawn(pythonBin(runtime), ['-I', '-B', '-m', 'deploom_mcp'], {
      stdio: 'inherit', windowsHide: true, env,
    });
    try {
      await new Promise((resolve, reject) => {
        child.once('spawn', resolve);
        child.once('error', reject);
      });
    } catch (error) {
      fs.unlinkSync(starting);
      throw error;
    }
    const lease = path.join(leases, String(child.pid));
    fs.renameSync(starting, lease);
    child.once('exit', code => {
      fs.rmSync(lease, { force: true });
      process.exitCode = code ?? 1;
    });
  });
}

module.exports = { versionPattern, withLock, pythonBin, sitePackages };
if (require.main === module) launch(__dirname).catch(err => { console.error(err.message); process.exitCode = 1; });
