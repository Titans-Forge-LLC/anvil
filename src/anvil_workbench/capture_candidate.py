"""Capture an operator-supplied candidate in the existing private job format.

No repair recipes, model calls, check execution, application or approval.
"""

import argparse
import ast
import json
from pathlib import Path
import time

from .proposal_checks import digest, read_bounded, relative_file
from .workbench import (
    OfflineCompletion,
    ProposalSession,
    _job_replay,
    _job_function_span,
)


def capture(
    project_root,
    source_file,
    candidate_file,
    symbol,
    intent_file,
    output,
    expected_source_sha256,
    *,
    context_symbols=(),
    check_failed=False,
):
    """Import one top-level Python function's change, retaining no test success.

    The caller supplies the solution. Structural scope checks do not prove its
    behavior. Inputs/capsules are private, untrusted history; checks stay fresh.
    """
    started = time.perf_counter()
    root = Path(project_root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError('project_root must be a directory')
    if type(check_failed) is not bool:
        raise ValueError('check_failed must be a boolean')
    if (
        type(expected_source_sha256) is not str
        or len(expected_source_sha256) != 64
        or any(c not in '0123456789abcdef' for c in expected_source_sha256)
    ):
        raise ValueError('explicit source SHA-256 required')
    if type(symbol) is not str or not symbol.isidentifier():
        raise ValueError('select one top-level Python function')
    if (
        not isinstance(context_symbols, (list, tuple))
        or len(context_symbols) > 4
        or any(
            type(n) is not str or not n.isidentifier() or n == symbol
            for n in context_symbols
        )
        or len(set(context_symbols)) != len(context_symbols)
    ):
        raise ValueError('declare up to four distinct helper function names')
    paths = [relative_file(root, n) for n in (source_file, candidate_file, intent_file)]
    if len(set(paths)) != 3:
        raise ValueError('source, candidate and intent must be distinct files')
    source_path, candidate_path, intent_path = paths
    if source_path.suffix != '.py':
        raise ValueError('source must be Python')
    raw = read_bounded(source_path)
    candidate_raw = read_bounded(candidate_path)
    intent_raw = read_bounded(intent_path, 16384)
    if digest(raw) != expected_source_sha256:
        raise ValueError('source changed since selection')
    source = raw.decode('utf-8')
    candidate = candidate_raw.decode('utf-8')
    intent = intent_raw.decode('utf-8')
    if any('\x00' in t for t in (source, candidate, intent)):
        raise ValueError('NUL input rejected')
    if not intent.strip() or len(intent) > 4000:
        raise ValueError('intent must contain 1..4000 characters')
    if candidate_raw == raw:
        raise ValueError('candidate has no change to retain')

    # Importing a candidate preserves the selected API; no implicit API redesign.
    def signature(text):
        function = ast.parse(
            _job_function_span(text, symbol)[2], type_comments=True
        ).body[0]
        function.body = [ast.Pass()]
        return ast.dump(function)

    if signature(source) != signature(candidate):
        raise ValueError('selected function signature changed')
    # Reuse existing structural scope/environment checks, not another edit engine.
    _job_replay(
        source_path, source, candidate, symbol, list(context_symbols), digest(raw)
    )
    if any(
        read_bounded(p, limit) != data
        for p, data, limit in (
            (source_path, raw, 1048576),
            (candidate_path, candidate_raw, 1048576),
            (intent_path, intent_raw, 16384),
        )
    ):
        raise ValueError('capture input changed during validation')
    session = ProposalSession(OfflineCompletion())
    session.proposals['operator-candidate'] = dict(
        file=str(source_path),
        symbol=symbol,
        symbols=None,
        text=candidate,
        source_sha256=digest(raw),
        format='replacement',
        context_symbols=list(context_symbols),
        original_instruction=intent,
    )
    if check_failed:
        proposal = session.proposals['operator-candidate']
        proposal['quarantined'] = True
        proposal['historical_notes_untrusted'] = {
            'untrusted': True,
            'check_summary': 'Operator reported a failed check.',
            'test_plan_sha256': None,
            'reported_check': 'failed',
        }
    destination = Path(output)
    if destination.is_absolute() or any(p in ('..',) for p in destination.parts):
        raise ValueError('capsule output must stay inside the project')
    saved = session.save_job(
        'operator-candidate', root, root / destination, instruction=intent
    )
    return dict(
        saved,
        schema='anvil-operator-candidate-capture-v1',
        source_sha256=digest(raw),
        candidate_sha256=digest(candidate_raw),
        intent_sha256=digest(intent_raw),
        input_kind='operator_supplied_full_candidate',
        tests='not_run',
        semantic_certificate=False,
        quarantined=check_failed,
        fresh_checks_required=True,
        fresh_review_required=True,
        elapsed_seconds=time.perf_counter() - started,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        'project-root',
        'source',
        'candidate',
        'symbol',
        'intent-file',
        'output',
        'source-sha256',
    ):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--context-symbol', action='append', default=[])
    parser.add_argument(
        '--check-failed',
        action='store_true',
        help='record a known failure and block draft export',
    )
    args = parser.parse_args(argv)
    try:
        result = capture(
            args.project_root,
            args.source,
            args.candidate,
            args.symbol,
            args.intent_file,
            args.output,
            args.source_sha256,
            context_symbols=args.context_symbol,
            check_failed=args.check_failed,
        )
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (
        OSError,
        ValueError,
        RuntimeError,
        UnicodeError,
        SyntaxError,
        RecursionError,
    ) as exc:
        print(
            json.dumps(
                dict(
                    status='refused',
                    error=str(exc),
                    model_requests=0,
                    applied=False,
                    approved=False,
                )
            )
        )
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
