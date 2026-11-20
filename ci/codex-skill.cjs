'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { createInterface } = require('node:readline');

async function check() {
  const profile = path.resolve(process.argv[2]);
  const app = spawn(process.env.ComSpec || 'cmd.exe', ['/d', '/c', 'codex app-server --listen stdio://'], {
    cwd: profile, windowsHide: true, stdio: ['pipe', 'pipe', 'inherit'],
    env: { ...process.env, USERPROFILE: profile, CODEX_HOME: path.join(profile, '.codex') },
  });
  const timer = setTimeout(() => app.kill(), 45000);
  const send = packet => app.stdin.write(JSON.stringify(packet) + '\n');
  try {
    send({ id: 1, method: 'initialize', params: { clientInfo: { name: 'deploom-smoke', version: '1' } } });
    for await (const line of createInterface({ input: app.stdout })) {
      const packet = JSON.parse(line);
      if (packet.error) throw Error(JSON.stringify(packet.error));
      if (packet.id === 1) {
        send({ method: 'initialized' });
        send({ id: 2, method: 'skills/list', params: { cwds: [profile], forceReload: true } });
      }
      if (packet.id === 2) {
        const target = path.join(profile, '.agents/skills/deploom-upgrade/SKILL.md');
        const skills = packet.result.data.flatMap(entry => entry.skills);
        const found = skills.some(s => s.name === 'deploom-upgrade' && s.enabled &&
          fs.realpathSync.native(s.path).toLowerCase() === fs.realpathSync.native(target).toLowerCase());
        if (!found) throw Error('Installed Skill was absent from the Codex skill list');
        console.log('Codex discovered the installed Skill');
        return;
      }
    }
    throw Error('Codex exited before reporting skills');
  } finally { clearTimeout(timer); app.stdin.end(); app.kill(); }
}
check().catch(error => { console.error(error.message); process.exitCode = 1; });
