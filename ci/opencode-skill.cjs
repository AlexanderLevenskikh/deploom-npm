// OpenCode 2 registers skills and MCP connections asynchronously after the first request.
const { spawn } = require('node:child_process');
const { randomUUID } = require('node:crypto');
const { createInterface } = require('node:readline');
const path = require('node:path');
const assert = require('node:assert/strict');

async function main() {
  const password = randomUUID();
  const server = spawn(
    'opencode',
    ['serve', '--stdio', '--hostname', '127.0.0.1', '--port', '0'],
    {
      windowsHide: true,
      stdio: ['pipe', 'pipe', 'inherit'],
      env: {
        ...process.env,
        OPENCODE_SERVER_PASSWORD: password,
        OPENCODE_PASSWORD: password,
      },
    },
  );
  const timeout = setTimeout(() => server.kill(), 60000);
  try {
    const lines = createInterface({ input: server.stdout });
    const first = await lines[Symbol.asyncIterator]().next();
    assert(!first.done, 'OpenCode exited before announcing its address');
    const base = new URL(JSON.parse(first.value).url);
    assert.equal(base.hostname, '127.0.0.1');
    const headers = {
      Authorization:
        'Basic ' + Buffer.from('opencode:' + password).toString('base64'),
    };
    const expected = path.join(
      process.env.OPENCODE_CONFIG_DIR,
      'skills',
      'deploom-upgrade',
      'SKILL.md',
    );
    async function get(route) {
      const response = await fetch(new URL(route, base), {
        headers,
        signal: AbortSignal.timeout(5000),
      });
      assert(response.ok, route + ' returned ' + response.status);
      return (await response.json()).data;
    }
    const deadline = Date.now() + 45000;
    while (Date.now() < deadline) {
      const [mcps, skills] = await Promise.all([
        get('/api/mcp'),
        get('/api/skill'),
      ]);
      const connected = mcps.some(
        (m) => m.name === 'deploom' && m.status.status === 'connected',
      );
      const loaded = skills.some(
        (s) =>
          s.name === 'deploom-upgrade' &&
          path.resolve(s.path) === path.resolve(expected),
      );
      if (connected && loaded) {
        console.log('OpenCode: deploom connected; installed skill discovered.');
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    throw Error(
      'OpenCode did not register the installed skill and MCP within 45s',
    );
  } finally {
    clearTimeout(timeout);
    server.stdin.end();
    server.kill();
  }
}
main().catch((e) => {
  console.error(e.message);
  process.exitCode = 1;
});
