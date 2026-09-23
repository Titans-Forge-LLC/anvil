import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {migrate} from '../scripts/migrate_legacy_browser.mjs';
import * as old from '../site/codec-legacy.mjs';
import * as current from '../site/codec.mjs';

const cases = [
  {'10': 1, '2': 2}, {'a\u{10000}': 1, 'a\ue000': 2},
  JSON.parse('{"__proto__":{"permits":[]},"authority":{"forbids":[{"kind":"publish","target":"*"}]}}'),
  {'version': '0.1', '@0': '#0', 'nested': [{'2': 1, '10': 3}]},
  null, {'value': 1.5, 'small': 1e-7}, {'a': 'unchanged'}
];
let changed = 0;
for (const value of cases) {
  const result = migrate(old.encode(value));
  assert.deepEqual(current.decode(result.wire), value);
  assert.equal(result.wire, current.encode(value));
  assert.equal(migrate(result.wire).changed, false);
  changed += Number(result.changed);
}
const prefix = `AVP1|${current.PROFILE_ID}|`;
const invalid = [
  'AVP1|wrong|{}', prefix + '{"a":1,"a":2}', prefix + '{"@0":1,"version":2}',
  prefix + '{ "a":1}', prefix + '{"a":9007199254740993}', prefix + '{"a":1e999}',
  prefix + '{"a":', prefix + '{}\n\n', prefix + '{"a":1.00}', prefix + '{"a":"\\u0061"}',
  'x'.repeat(1024 * 1024 + 1)
];
for (const wire of invalid) assert.throws(() => migrate(wire));
const command = fileURLToPath(new URL('../scripts/migrate_legacy_browser.mjs', import.meta.url));
const pass = spawnSync(process.execPath, [command], {input: old.encode(cases[0]) + '\n', encoding:'utf8'});
assert.equal(pass.status, 0);
assert.equal(pass.stdout, current.encode(cases[0]) + '\n');
assert.equal(JSON.parse(pass.stderr).changed, true);
const fail = spawnSync(process.execPath, [command], {input: invalid[1], encoding:'utf8'});
assert.equal(fail.status, 1); assert.equal(fail.stdout, '');
console.log(JSON.stringify({roundtrips: cases.length, changed, rejections: invalid.length,
  cli_success: true, cli_refusal: true, model_calls: 0}));
