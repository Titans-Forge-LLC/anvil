// Explicit offline conversion, not a permissive replacement for normal decode.
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import * as current from '../site/codec.mjs';
import * as legacy from '../site/codec-legacy.mjs';

export function migrate(wire) {
  if (typeof wire !== 'string' || Buffer.byteLength(wire, 'utf8') > 1024 * 1024) {
    throw new Error('Expected an AVP1 wire of at most 1 MiB');
  }
  const prefix = `AVP1|${current.PROFILE_ID}|`;
  if (!wire.startsWith(prefix)) throw new Error('Wrong wire version or context');
  // Parsing does not grant acceptance. Both canonicality checks below are required.
  const packed = JSON.parse(wire.slice(prefix.length));
  const canonicalPacked = current.canonicalJson(packed);
  const decoded = current.decode(prefix + canonicalPacked);
  const output = current.encode(decoded);
  // Exact re-encoding rejects duplicate JSON keys, collisions, alternate escapes,
  // numeric precision loss and arbitrary noncanonical forms. Accept current wires
  // too, so explicit migration is idempotent.
  if (wire !== output && legacy.encode(decoded) !== wire) {
    throw new Error('Not an exact legacy-browser or current canonical wire');
  }
  if (current.canonicalJson(current.decode(output)) !== current.canonicalJson(decoded)) {
    throw new Error('Semantic verification failed');
  }
  return {wire: output, changed: wire !== output,
    source_sha256: createHash('sha256').update(wire).digest('hex'),
    output_sha256: createHash('sha256').update(output).digest('hex')};
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    // Bounded stdin read; no implicit filesystem reads or writes of user payloads.
    const buffer = Buffer.alloc(1024 * 1024 + 1);
    const {readSync} = await import('node:fs');
    let length = 0, count;
    while (length < buffer.length && (count = readSync(0, buffer, length, buffer.length - length, null)) > 0) length += count;
    if (length > 1024 * 1024) throw new Error('Input exceeds 1 MiB');
    const input = new TextDecoder('utf-8', {fatal: true}).decode(buffer.subarray(0, length));
    // The CLI alone permits the single final LF added by pipe-oriented writers.
    const result = migrate(input.endsWith('\n') ? input.slice(0, -1) : input);
    process.stdout.write(result.wire + '\n');
    process.stderr.write(JSON.stringify({changed: result.changed,
      source_sha256: result.source_sha256, output_sha256: result.output_sha256}) + '\n');
  } catch {
    process.stderr.write('Migration refused: invalid, unsupported, or noncanonical wire.\n');
    process.exitCode = 1;
  }
}
