(function () {
  'use strict';
  const PROFILE_ID = 'governed-mission-v1';
  const PREFIX = 'AVP1';
  const KEYS = [
    'version', 'mission', 'inputs', 'steps', 'outputs', 'authority', 'name',
    'type', 'ref', 'op', 'bind', 'args', 'effects', 'permits', 'forbids',
    'requirements', 'kind', 'target', 'gate', 'approval', 'evidence', 'mode',
    'effect', 'condition', 'value', 'count', 'require'
  ];
  const VALUES = [
    '0.1', 'read', 'write', 'publish', 'human', 'exact_text', 'gate',
    'approval', 'source', 'staging', 'content', 'pass', 'review_pass'
  ];
  const keyToSymbol = new Map(KEYS.map((key, index) => [key, `@${index.toString(16)}`]));
  const symbolToKey = new Map([...keyToSymbol].map(([key, value]) => [value, key]));
  const valueToSymbol = new Map(VALUES.map((value, index) => [value, `#${index.toString(16)}`]));
  const symbolToValue = new Map([...valueToSymbol].map(([key, value]) => [value, key]));

  class CodecError extends Error {}
  class ContextMismatchError extends CodecError {}

  function normalize(value) {
    if (value === null || typeof value === 'boolean' || typeof value === 'string') return value;
    if (typeof value === 'number') {
      if (!Number.isFinite(value)) throw new CodecError('non-finite JSON numbers are not supported');
      return value;
    }
    if (Array.isArray(value)) return value.map(normalize);
    if (typeof value === 'object') {
      return Object.fromEntries(Object.keys(value).sort().map((key) => [key, normalize(value[key])]));
    }
    throw new CodecError(`unsupported JSON type: ${typeof value}`);
  }

  function canonicalJson(value) { return JSON.stringify(normalize(value)); }
  function encodeKey(key) {
    if (keyToSymbol.has(key)) return keyToSymbol.get(key);
    return key.startsWith('@') ? `@${key}` : key;
  }
  function decodeKey(key) {
    if (symbolToKey.has(key)) return symbolToKey.get(key);
    return key.startsWith('@@') ? key.slice(1) : key;
  }
  function pack(value) {
    if (typeof value === 'string') {
      if (valueToSymbol.has(value)) return valueToSymbol.get(value);
      return value.startsWith('#') ? `#${value}` : value;
    }
    if (Array.isArray(value)) return value.map(pack);
    if (value && typeof value === 'object') {
      return Object.fromEntries(Object.entries(value)
        .map(([key, item]) => [encodeKey(key), pack(item)])
        .sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0));
    }
    return value;
  }
  function unpack(value) {
    if (typeof value === 'string') {
      if (symbolToValue.has(value)) return symbolToValue.get(value);
      return value.startsWith('##') ? value.slice(1) : value;
    }
    if (Array.isArray(value)) return value.map(unpack);
    if (value && typeof value === 'object') {
      const result = {};
      for (const [key, item] of Object.entries(value)) {
        const decodedKey = decodeKey(key);
        if (Object.hasOwn(result, decodedKey)) throw new CodecError(`decoded key collision: ${decodedKey}`);
        result[decodedKey] = unpack(item);
      }
      return result;
    }
    return value;
  }
  function encode(value, profileId = PROFILE_ID) {
    return `${PREFIX}|${profileId}|${JSON.stringify(pack(normalize(value)))}`;
  }
  function decode(wire, profileId = PROFILE_ID) {
    const first = wire.indexOf('|');
    const second = wire.indexOf('|', first + 1);
    if (first < 0 || second < 0 || wire.slice(0, first) !== PREFIX) throw new CodecError('invalid AVP1 wire header');
    const actualProfile = wire.slice(first + 1, second);
    if (actualProfile !== profileId) throw new ContextMismatchError(`profile mismatch: expected ${profileId}, got ${actualProfile}`);
    let packed;
    try { packed = JSON.parse(wire.slice(second + 1)); }
    catch { throw new CodecError('invalid AVP1 JSON body'); }
    const decoded = normalize(unpack(packed));
    if (encode(decoded, profileId) !== wire) throw new CodecError('AVP1 message is non-canonical');
    return decoded;
  }
  async function sha256(value) {
    const bytes = new TextEncoder().encode(canonicalJson(value));
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    return [...new Uint8Array(digest)].map((part) => part.toString(16).padStart(2, '0')).join('');
  }
  window.ANVIL_AVP1 = { PROFILE_ID, CodecError, ContextMismatchError, normalize, canonicalJson, encode, decode, sha256 };
}());
