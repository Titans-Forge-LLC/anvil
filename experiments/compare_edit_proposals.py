"""Small public-code screen of whole-function versus exact-span proposals.

Uses an existing local Splash server. Does not install, start, apply or execute.
Prints metadata only. Structural edit failures get one counted replacement
fallback; task checks are an evaluator, never runtime authorization.
"""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import time

from workbench import SplashCompletion, propose
from compare_source_drafts import TASKS

ROOT = Path(__file__).resolve().parents[1]


def correct(symbol, original, replacement):
    if replacement is None:
        return False
    try:
        before = ast.parse(original)
        after = ast.parse(replacement)
        expected = copy.deepcopy(before)
        node = next(n for n in expected.body if isinstance(n, ast.FunctionDef) and n.name == symbol)
        actual = next(n for n in after.body if isinstance(n, ast.FunctionDef) and n.name == symbol)
        if symbol == '_load_json':
            for child in ast.walk(node):
                if isinstance(child, ast.Constant) and child.value == 'utf-8':
                    child.value = 'utf-8-sig'
        elif symbol == '_pack':
            first = actual.body[0]
            if not (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str) and first.value.value):
                return False
            actual.body = actual.body[1:]
        elif symbol == 'normalize':
            branch = next(n for n in node.body if isinstance(n, ast.If)
                          and isinstance(n.test, ast.Call) and len(n.test.args) == 2
                          and isinstance(n.test.args[1], ast.Name) and n.test.args[1].id == 'Mapping')
            branch.body = branch.body[:1] + ast.parse('return {key: normalize(value[key]) for key in sorted(value)}').body
        else:
            return False
        return ast.dump(expected) == ast.dump(after)
    except (SyntaxError, ValueError, StopIteration, IndexError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--splash-url', default='http://127.0.0.1:8000')
    parser.add_argument('--model')
    args = parser.parse_args()
    started = time.perf_counter()
    completion = SplashCompletion(args.splash_url, args.model)
    rows = []
    for repeat, order in enumerate((('replacement', 'edit'), ('edit', 'replacement'))):
        for mode in order:
            for symbol, filename, instruction in TASKS:
                path = ROOT / filename
                original = path.read_bytes().decode('utf-8')
                request = dict(file=str(path), symbol=symbol, instruction=instruction,
                               max_tokens=512, format=mode)
                attempts = []
                task_start = time.perf_counter()
                result = propose(completion, request)
                first_correct = correct(symbol, original, result['replacement_text'])
                attempts.append(result)
                if mode == 'edit' and not result['reviewable']:
                    result = propose(completion, dict(request, format='replacement'))
                    attempts.append(result)
                row = dict(repetition=repeat, mode=mode, task=symbol,
                    first_pass_correct=first_correct,
                    final_correct=correct(symbol, original, result['replacement_text']),
                    first_pass_reviewable=attempts[0]['reviewable'],
                    fallback=len(attempts) > 1, http_requests=len(attempts),
                    task_seconds=time.perf_counter() - task_start,
                    proposal_seconds=sum(r['total_request_seconds'] for r in attempts),
                    output_tokens=sum(r['output_tokens'] for r in attempts),
                    output_bytes=sum(len(r['text'].encode('utf-8')) for r in attempts),
                    source_sha256=hashlib.sha256(original.encode('utf-8')).hexdigest(),
                    replacement_sha256=hashlib.sha256(result['replacement_text'].encode('utf-8')).hexdigest()
                        if result['replacement_text'] is not None else None)
                rows.append(row)
                print(json.dumps({'request': row}), flush=True)
    print(json.dumps({'summary': dict(rows=rows,
        campaign_seconds=time.perf_counter() - started, startup_included=False,
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        workbench_sha256=hashlib.sha256((ROOT / 'experiments/workbench.py').read_bytes()).hexdigest(),
        scope='three known public tasks, reversed order, one shared warm server; not independent tasks or a job benchmark',
        code_applied=False, code_executed=False)}), flush=True)


if __name__ == '__main__':
    main()
