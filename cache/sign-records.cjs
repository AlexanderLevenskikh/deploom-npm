'use strict';
const {createHash, createPrivateKey, createPublicKey, sign, verify} = require('node:crypto');
const fs = require('node:fs');
const [cache, sigFile, pin] = process.argv.slice(2);
const raw = fs.readFileSync(cache);
if (raw.length > 2000000) throw Error('Cache exceeds MCP limit');
const encoded = process.env.DEPLOOM_RECORDS_SIGNING_KEY;
delete process.env.DEPLOOM_RECORDS_SIGNING_KEY;
const key = createPrivateKey({format:'der', type:'pkcs8', key: Buffer.from(encoded, 'base64')});
const publicKey = createPublicKey(key);
const expected = fs.readFileSync(pin, 'ascii').trim();
if (key.asymmetricKeyType !== 'ed25519' || Buffer.from(publicKey.export({format:'jwk'}).x, 'base64url').toString('hex') !== expected) {
  throw Error('The environment key does not match the consumer pin');
}
const message = Buffer.concat([Buffer.from('DepLoom public migration records v1\0'), createHash('sha256').update(raw).digest()]);
const signature = sign(null, message, key);
if (!verify(null, message, publicKey, signature)) throw Error('Signature self-check failed');
fs.writeFileSync(sigFile, signature, {flag:'wx'});
