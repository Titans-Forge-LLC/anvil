"""Small first-request comparison, not a general coding benchmark.

Run from a checkout with --model /existing/local/MLX/model. No code is applied
or executed. Prints metadata and output hashes, never source/proposal bodies.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from workbench import Completion, MLXBackend, propose


ROOT = Path(__file__).resolve().parents[1]
TASKS = (
    ('normalize', 'src/anvil_alpha/codec.py',
     'Replace only the normalized mapping accumulation loop with a dict comprehension. '
     'Keep key validation before sorting, docstring, annotations and all other behavior.'),
    ('_load_json', 'src/anvil_alpha/cli.py',
     'Accept UTF-8 JSON files with or without a byte order mark using utf-8-sig encoding. '
     'Preserve all other behavior and annotations.'),
    ('_pack', 'src/anvil_alpha/codec.py',
     'Add a concise one-line docstring describing what this function does. '
     'Keep all executable code and annotations unchanged.'),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    backend = MLXBackend(args.model)
    rows = []
    for repeat, order in enumerate((('ordinary', 'source'), ('source', 'ordinary'))):
        for mode in order:
            for symbol, filename, instruction in TASKS:
                # Empty session for every task: no repeat-response cache advantage.
                completion = Completion(backend, mode == 'source', mode == 'source')
                result = propose(completion, {'file': str(ROOT / filename),
                                 'symbol': symbol, 'instruction': instruction, 'max_tokens': 512})
                row = {key: result[key] for key in (
                    'total_request_seconds', 'complete', 'reviewable', 'source_sha256',
                    'output_tokens', 'model_calls', 'draft_tokens_verified', 'draft_tokens_scored')}
                row.update(repetition=repeat, mode=mode, task=symbol,
                           output_sha256=hashlib.sha256(result['text'].encode()).hexdigest())
                rows.append(row)
                print(json.dumps({'request': row}), flush=True)
                del completion
                backend.mx.clear_cache()
    pairs = []
    for repeat in range(2):
        for symbol, _, _ in TASKS:
            pair = [row for row in rows if row['repetition'] == repeat and row['task'] == symbol]
            pairs.append({'repetition': repeat, 'task': symbol,
                          'equal_text': pair[0]['output_sha256'] == pair[1]['output_sha256'],
                          'both_complete': all(row['complete'] for row in pair)})
    print(json.dumps({'summary': {
        'pairs': pairs,
        'request_seconds': {mode: sum(r['total_request_seconds'] for r in rows if r['mode'] == mode)
                            for mode in ('ordinary', 'source')},
        'shared_load_seconds': backend.load_seconds,
        'campaign_seconds': time.perf_counter() - started,
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'workbench_sha256': hashlib.sha256((ROOT / 'experiments/workbench.py').read_bytes()).hexdigest(),
        'scope': 'three authored first-edit requests, two reversed-order repetitions; no behavior execution',
    }}), flush=True)


if __name__ == '__main__':
    main()
