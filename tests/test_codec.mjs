import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
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

const fixture = JSON.parse(readFileSync(new URL('../examples/governed_mission.json', import.meta.url), 'utf8'));
const python = spawnSync(
  process.env.PYTHON || 'python3',
  ['-c', 'import json,sys; from anvil_alpha import AVP1Codec; print(AVP1Codec().encode(json.load(sys.stdin)), end="")'],
  { input: JSON.stringify(fixture), encoding: 'utf8', env: { ...process.env, PYTHONPATH: 'src' } }
);
assert.equal(python.status, 0, python.stderr);
assert.equal(encode(fixture), python.stdout);
assert.deepEqual(decode(python.stdout), fixture);
console.log('browser codec tests passed');
