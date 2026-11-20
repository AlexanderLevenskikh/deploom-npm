'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { read, locations } = require('./launch.cjs');
const { execFileSync } = require('node:child_process');
const jsonc = require('../vendor/jsonc-parser');

function prepareConfig(client, launcher, scratch) {
  const { file, skill } = locations(client);
  if (client === 'codex') {
    const before = read(file, '');
    const copied = path.join(scratch, 'config.toml');
    fs.writeFileSync(copied, before);
    const list = () => JSON.parse(execFileSync(process.env.ComSpec || 'cmd.exe', ['/d', '/c', 'codex mcp list --json'], {
      env: { ...process.env, CODEX_HOME: scratch }, cwd: scratch, encoding: 'utf8', windowsHide: true,
    })).find(entry => entry.name === 'deploom');
    const matches = entry => entry?.enabled && entry.transport?.type === 'stdio' &&
      entry.transport.command === 'node' && JSON.stringify(entry.transport.args) === JSON.stringify([launcher]);
    const existing = list();
    const eol = before.includes('\r\n') ? '\r\n' : '\n';
    let after = before;
    if (!existing) {
      after += [before ? eol : '', '[mcp_servers.deploom]', 'command = "node"',
        'args = [' + JSON.stringify(launcher) + ']', ''].join(eol);
      fs.writeFileSync(copied, after);
    }
    if (!matches(existing || list())) throw Error('Conflicting Codex MCP entry');
    return { file, before, after, skill };
  }
  const claude = client === 'claude';
  let keys, entry;
  if (claude) {
    keys = ['mcpServers', 'deploom'];
    entry = { type: 'stdio', command: 'node', args: [launcher] };
  } else {
    const version = execFileSync(process.env.ComSpec || 'cmd.exe', ['/d', '/c', 'opencode --version'], { encoding: 'utf8', windowsHide: true }).trim();
    const major = /^(?:opencode\s+)?v?([12])\./m.exec(version)?.[1];
    if (!major) throw Error('Supported OpenCode versions are 1.x and 2.x');
    keys = major === '2' ? ['mcp', 'servers', 'deploom'] : ['mcp', 'deploom'];
    entry = { type: 'local', command: ['node', launcher], ...(major === '2' ? { disabled: false } : { enabled: true }) };
  }
  const before = read(file, '{}\n');
  const bom = before.startsWith('\uFEFF') ? '\uFEFF' : '';
  const text = before.slice(bom.length);
  const errors = [];
  const config = claude ? JSON.parse(text) : jsonc.parse(text, errors, { allowTrailingComma: true });
  if (errors.length || !config || typeof config !== 'object' || Array.isArray(config)) throw Error('Invalid client settings');
  let current = config;
  for (const key of keys) {
    if (current === undefined) break;
    if (!current || typeof current !== 'object' || Array.isArray(current)) throw Error('Invalid MCP settings');
    current = current[key];
  }
  if (current !== undefined && (!current || Object.entries(entry).some(([k, v]) =>
    JSON.stringify(current[k]) !== JSON.stringify(v)))) throw Error('Conflicting MCP entry: ' + client);
  const after = current !== undefined ? before : bom + jsonc.applyEdits(text, jsonc.modify(text, keys, entry, {
    formattingOptions: { insertSpaces: true, tabSize: 2, eol: text.includes('\r\n') ? '\r\n' : '\n' },
  }));
  return { file, before, after, skill };
}
module.exports = { prepareConfig };
