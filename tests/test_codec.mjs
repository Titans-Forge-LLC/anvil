import assert from 'node:assert/strict';
import { ContextMismatchError, canonicalJson, decode, encode } from '../site/codec.mjs';

const sample = {
  authority: { forbids: [{ kind: 'publish', target: '*' }], permits: [{ kind: 'read', target: 'source' }] },
  mission: 'test',
  version: '0.1'
};

const wire = encode(sample);
assert.equal(canonicalJson(decode(wire)), canonicalJson(sample));
assert.throws(() => decode(wire, 'wrong-profile'), ContextMismatchError);
assert.deepEqual(decode(encode({ '@0': '#0', version: '0.1' })), { '@0': '#0', version: '0.1' });
console.log('browser codec tests passed');
