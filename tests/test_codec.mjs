import assert from 'node:assert/strict';
import { CodecError, ContextMismatchError, canonicalJson, decode, encode } from '../site/codec.mjs';

const sample = {
  authority: { forbids: [{ kind: 'publish', target: '*' }], permits: [{ kind: 'read', target: 'source' }] },
  mission: 'test',
  version: '0.1'
};

const wire = encode(sample);
assert.equal(canonicalJson(decode(wire)), canonicalJson(sample));
assert.throws(() => decode(wire, 'wrong-profile'), ContextMismatchError);
assert.deepEqual(decode(encode({ '@0': '#0', version: '0.1' })), { '@0': '#0', version: '0.1' });
assert.equal(canonicalJson({'10': 1, '2': 2}), '{"10":1,"2":2}');
assert.equal(canonicalJson({'a\u{10000}': 1, 'a\ue000': 2, '': 3}), '{"":3,"a\ue000":2,"a\u{10000}":1}');
const properties = JSON.parse('{"__proto__":{"polluted":true},"constructor":"data"}');
assert.deepEqual(decode(encode(properties)), properties);
assert.equal({}.polluted, undefined);
assert.equal(canonicalJson(properties), '{"__proto__":{"polluted":true},"constructor":"data"}');
assert.throws(() => decode('AVP1|governed-mission-v1|{"@0":1,"version":2}'), CodecError);
// Old JavaScript-only key order is not the canonical Python-compatible wire.
assert.throws(() => decode('AVP1|governed-mission-v1|{"2":2,"10":1}'), CodecError);
// Do not adopt the experimental serializer's narrower numeric domain.
for (const number of [1.5, -0, 1e-7, 1e21, 9007199254740992]) {
  assert.equal(canonicalJson(number), JSON.stringify(number));
  assert.equal(encode(number), `AVP1|governed-mission-v1|${JSON.stringify(number)}`);
  assert.equal(canonicalJson(decode(encode(number))), JSON.stringify(number));
}
assert.equal(canonicalJson(new Array(2)), '[null,null]');
for (const value of [NaN, Infinity, undefined]) assert.throws(() => encode(value), CodecError);
console.log('browser codec tests passed');
