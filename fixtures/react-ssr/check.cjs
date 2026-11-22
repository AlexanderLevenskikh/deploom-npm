// Run the same server-render check before and after upgrading React and react-dom.
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const demo = fs.mkdtempSync(path.join(os.tmpdir(), 'deploom-react-ssr-'));
const test = `
  const assert = require('node:assert/strict');
  const React = require('react');
  const { renderToStaticMarkup } = require('react-dom/server');
  assert.equal(React.version, process.argv[2]);
  assert.equal(require('react-dom/package.json').version, React.version);
  assert.equal(renderToStaticMarkup(React.createElement('h1', null, 'Hello DepLoom')), '<h1>Hello DepLoom</h1>');
`;
try {
  fs.writeFileSync(path.join(demo, 'test.cjs'), test);
  for (const version of ['18.2.0', '18.3.1']) {
    fs.writeFileSync(path.join(demo, 'package.json'), JSON.stringify({
      name: 'react-ssr-fixture', private: true, dependencies: { react: version, 'react-dom': version },
    }));
    const args = ['install', '--registry=https://registry.npmjs.org/', '--strict-peer-deps',
      '--ignore-scripts', '--no-audit', '--no-fund'];
    const windows = process.platform === 'win32';
    execFileSync(windows ? process.env.ComSpec : 'npm', windows ? ['/d', '/c', 'npm.cmd', ...args] : args,
      { cwd: demo, stdio: 'inherit', timeout: 120000 });
    execFileSync(process.execPath, ['test.cjs', version], { cwd: demo, stdio: 'inherit', timeout: 30000 });
    console.log('SSR passed with React', version);
  }
} finally {
  fs.rmSync(demo, { recursive: true, force: true });
}
