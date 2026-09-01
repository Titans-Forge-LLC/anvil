import { PROFILE_ID, canonicalJson, decode, encode, sha256 } from './codec.mjs';

const defaultMission = {
  authority: {
    forbids: [{ kind: 'publish', target: '*' }],
    permits: [{ kind: 'read', target: 'source' }, { kind: 'write', target: 'staging' }],
    requirements: [
      { effect: { kind: 'write', target: 'staging' }, gate: 'review_pass', kind: 'gate' },
      { effect: { kind: 'publish', target: 'content' }, kind: 'approval', mode: 'exact_text', target: 'human' }
    ]
  },
  inputs: [{ name: 'source', ref: 'sha256:synthetic-source-pack', type: 'Artifact<SourcePack>' }],
  mission: 'governed_content',
  outputs: [{ name: 'staged_content', type: 'Artifact<StagedContent>' }],
  steps: [{
    args: { count: 3, require: ['url', 'quote', 'claim_boundary'], source: 'source' },
    bind: 'content',
    effects: [{ kind: 'write', target: 'staging' }],
    op: 'generate.content'
  }],
  version: '0.1'
};

const source = document.querySelector('#source-json');
const wire = document.querySelector('#wire-output');
const status = document.querySelector('#status');
const jsonBytes = document.querySelector('#json-bytes');
const wireBytes = document.querySelector('#wire-bytes');
const ratio = document.querySelector('#ratio');
const semanticHash = document.querySelector('#semantic-hash');
const authorityHash = document.querySelector('#authority-hash');
const encodeButton = document.querySelector('#encode');
const wrongContextButton = document.querySelector('#wrong-context');
const resetButton = document.querySelector('#reset');

const bytes = (text) => new TextEncoder().encode(text).length;

async function run(profile = PROFILE_ID) {
  try {
    const parsed = JSON.parse(source.value);
    const canonical = canonicalJson(parsed);
    const encoded = encode(parsed);
    const decoded = decode(encoded, profile);
    const exact = canonical === canonicalJson(decoded);
    wire.value = encoded;
    jsonBytes.textContent = bytes(canonical).toLocaleString();
    wireBytes.textContent = bytes(encoded).toLocaleString();
    ratio.textContent = `${(bytes(canonical) / bytes(encoded)).toFixed(4)}×`;
    semanticHash.textContent = await sha256(decoded);
    authorityHash.textContent = await sha256(decoded.authority);
    status.dataset.state = exact ? 'pass' : 'fail';
    status.textContent = exact ? 'Exact semantic and authority round trip' : 'Round trip failed';
  } catch (error) {
    status.dataset.state = 'fail';
    status.textContent = error.message;
    if (profile !== PROFILE_ID) wire.value = 'Decode refused. The bound profile does not match.';
  }
}

encodeButton.addEventListener('click', () => run());
wrongContextButton.addEventListener('click', () => run('wrong-profile'));
resetButton.addEventListener('click', () => {
  source.value = JSON.stringify(defaultMission, null, 2);
  run();
});

source.value = JSON.stringify(defaultMission, null, 2);
run();
