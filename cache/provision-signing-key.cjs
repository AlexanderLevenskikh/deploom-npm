// One-time provisioning. The only output on success is the raw public key as hex.
'use strict';
const { spawnSync } = require('node:child_process');
const { generateKeyPairSync } = require('node:crypto');

const repo = 'levencode-labs/deploom-npm';
const environment = 'cache-signing';
const name = 'DEPLOOM_RECORDS_SIGNING_KEY';
const endpoint = 'repos/' + repo + '/environments/' + environment;
const env = { ...process.env, GH_HOST: 'github.com', GH_PROMPT_DISABLED: '1' };
delete env.GH_DEBUG;
function read(path) {
  const result = spawnSync('gh', ['api', '--hostname', 'github.com', path], { env, encoding: 'utf8' });
  if (result.status !== 0) throw Error('Cannot read environment settings through GitHub API');
  return JSON.parse(result.stdout);
}
const policy = read(endpoint).deployment_branch_policy;
const rules = read(endpoint + '/deployment-branch-policies');
if (!policy?.custom_branch_policies || policy.protected_branches || rules.total_count !== 1 ||
    rules.branch_policies[0]?.type !== 'branch' || rules.branch_policies[0]?.name !== 'main') {
  throw Error('Expected exactly one deployment rule for branch main');
}
const secrets = read(endpoint + '/secrets?per_page=100');
if (secrets.total_count !== secrets.secrets.length || secrets.secrets.some(secret => secret.name === name)) {
  throw Error('Cannot verify that the signing key slot is empty');
}
const {privateKey, publicKey} = generateKeyPairSync('ed25519');
const der = privateKey.export({type: 'pkcs8', format: 'der'});
try {
  const result = spawnSync('gh', ['secret', 'set', name, '--env', environment, '--repo', 'github.com/' + repo], {
    input: der.toString('base64'), env, stdio: ['pipe', 'ignore', 'ignore'], windowsHide: true,
  });
  if (result.status !== 0) throw Error('GitHub did not confirm storing the key');
  console.log(Buffer.from(publicKey.export({format: 'jwk'}).x, 'base64url').toString('hex'));
} finally {
  der.fill(0);
}
