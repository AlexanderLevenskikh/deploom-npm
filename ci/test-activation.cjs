'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const [oldDir, newDir, root] = process.argv.slice(2).map(name => path.resolve(name));
if (!root || fs.existsSync(root)) throw Error('Specify two installed packages and a fresh test directory');
fs.mkdirSync(root, { recursive: true });
const env = { ...process.env, USERPROFILE: root, LOCALAPPDATA: path.join(root, 'local'),
  APPDATA: path.join(root, 'roaming'), CODEX_HOME: path.join(root, '.codex') };
const base = path.join(env.LOCALAPPDATA, 'DepLoom/public');
const profile = path.join(base, 'clients/codex');
const skill = path.join(root, '.agents/skills/deploom-upgrade');
const state = () => JSON.parse(fs.readFileSync(path.join(profile, 'active.json'), 'utf8'));
const readVersion = folder => JSON.parse(fs.readFileSync(path.join(folder, 'package.json'), 'utf8')).version;
const oldVersion = readVersion(oldDir), newVersion = readVersion(newDir);
assert.notEqual(oldVersion, newVersion);
fs.mkdirSync(env.CODEX_HOME, { recursive: true });
const configFile = path.join(env.CODEX_HOME, 'config.toml');
const baseline = '# local preferences\n[mcp_servers.example]\ncommand = "node"\n';
fs.writeFileSync(configFile, baseline);
function run(dir, cmd, expected = 0, nodeArgs = []) {
  const proc = spawnSync(process.execPath, [...nodeArgs, path.join(dir, 'bin/deploom.cjs'), cmd, 'codex'],
    { env, cwd: root, windowsHide: true, encoding: 'utf8', timeout: 240000 });
  if (proc.error) throw proc.error;
  assert.equal(proc.status, expected, proc.stderr);
}
run(oldDir, 'setup');
assert.equal(state().version, oldVersion);
const note = path.join(skill, 'local-notes.md');
fs.writeFileSync(note, 'user content');
const config = fs.readFileSync(configFile, 'utf8');
assert.ok(config.includes(baseline));
const injector = path.join(root, 'interrupt.cjs');
// Simulate process termination after the Skill directory moves but before activation commits.
fs.writeFileSync(injector, [
  "const fs = require('node:fs');",
  "const rename = fs.renameSync;",
  "fs.renameSync = function(from, to) {",
  "  const value = rename.apply(this, arguments);",
  "  if (to === " + JSON.stringify(skill) + " && from.startsWith(to + '.stage-')) process.exit(86);",
  "  return value;",
  "};",
].join('\n'));
run(newDir, 'setup', 86, ['--require', injector]);
assert.equal(state().version, oldVersion);
assert.ok(fs.existsSync(path.join(profile, 'transaction.json')));
run(newDir, 'setup');
assert.equal(state().version, newVersion);
assert.equal(state().previous, oldVersion);
assert.ok(!fs.existsSync(path.join(profile, 'transaction.json')));
assert.equal(fs.readFileSync(note, 'utf8'), 'user content');
assert.equal(JSON.parse(fs.readFileSync(path.join(skill, '.deploom-skill-install.json'), 'utf8')).target, skill);
run(newDir, 'rollback');
assert.equal(state().version, oldVersion);
assert.equal(state().previous, newVersion);
assert.equal(fs.readFileSync(note, 'utf8'), 'user content');
assert.equal(fs.readFileSync(configFile, 'utf8'), config);
const canonical = path.join(skill, 'SKILL.md');
fs.appendFileSync(canonical, '\nLocal change\n');
run(newDir, 'setup', 1);
assert.equal(state().version, oldVersion);
assert.ok(fs.readFileSync(canonical, 'utf8').endsWith('Local change\n'));
console.log(JSON.stringify({ oldVersion, newVersion, interrupted: true, recovered: true, rolledBack: true,
  preserved: ['clientConfig', 'userSkillFile', 'modifiedCanonicalFile'] }));
