"""Probe JBAI notice suggestions with synthetic public notices only.

Usage (from the repository root):
    .venv/bin/python -m demo.backend.tools.probe_jbai_notice [--json] [--all-modes]

The probe reads ``.env`` (values are never printed), sends the three synthetic
public notices that the tests already use through ``JbaiNoticeProvider`` and
prints one table: format mode, HTTP status, JSON/schema O/X, seconds and
suggestion counts. Keys, hosts, model names, request and response bodies are
kept in memory only and never printed, logged or written.

Format modes are tried in order: ``json_schema`` (strict, the provider
default) -> ``json_object`` -> ``prompt`` (no response_format, "JSON only"
instruction), built by the provider's own ``format_body`` with its automatic
fallback switched off so that each row measures exactly one mode. The first mode that answers HTTP 200 with schema-valid JSON is
used for the timed runs. ``--all-modes`` probes every mode once.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import socket
import sys
import time
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError

import pymupdf

from ..llm_drafts import _http_transport
from ..notice_analysis import analyze_notice
from ..notice_llm import (
    JSON_ONLY, MAX_RESPONSE, RESPONSE_FORMATS, RULE_TYPES, _canonical, _object_json, _quote_valid,
    _response, configured_notice_provider, enrich_notice, format_body, notice_payload,
)

ROOT = Path(__file__).resolve().parents[3]
MODES = RESPONSE_FORMATS
HARD_CALL_LIMIT = 15
apply_mode = format_body

# The three synthetic public notices below are copied verbatim from existing
# tests: A/B from tests/test_notice_analysis.py, C from tests/test_program_analysis.py.
NOTICES: dict[str, tuple[list[list[str]], str]] = {
    'A': ([[
        '2026 합성 청년 지원사업 모집 공고', '공고일: 2026. 11. 15.',
        '신청 기간: 2026. 11. 16. ~ 2026. 12. 15.', '지원 대상: 만 18세 이상 39세 이하 청년',
        '거주 요건: 전북특별자치도 거주자', '제출 서류: 주민등록초본, 건강보험료 납부확인서',
        '서류는 2026. 11. 15. 이후 발급분만 인정', '계속 근로 요건: 5개월 이상 연속 근로',
        '신청 방법: 온라인 신청', '문의: 합성청년센터 000-000-0000',
    ]], '합성 공개 부가 설명'),
    'B': ([['합성 청년 지원사업', '접수 기간: 2026-11-16 ~ 2026-12-31'],
           ['기준일: 2026-11-15', '자격: 만 18세 ~ 39세', '거주지: 전북 거주']], '합성 공개 부가 설명'),
    'C': ([['합성 청년 지원사업 모집', '공고일: 2026.11.01', '신청 기간: 2026.11.01 ~ 2026.12.15',
            '지원 대상: 1987.1.1 ~ 2008.12.31 출생자', '제출 서류: 면접용 사진사본',
            '신청 방법: 온라인 신청', '문의: 합성센터']], '합성 공개 부가 설명'),
}


def public_pdf(pages: list[list[str]]) -> bytes:
    with pymupdf.open() as document:
        for lines in pages:
            page = document.new_page(width=1000, height=1000)
            for index, line in enumerate(lines):
                page.insert_text((30, 40 + 24 * index), line, fontname='korea', fontsize=11)
        return document.tobytes()


class BudgetExceeded(Exception):
    pass


class Recorder:
    """Transport wrapper: enforces the call budget and records status/time only."""

    def __init__(self, inner: Callable[..., Mapping[str, Any]], budget: int):
        self.inner, self.budget, self.calls = inner, budget, 0
        self.last: dict[str, Any] = {}

    def __call__(self, url: str, headers: dict[str, str], body: dict[str, Any], timeout: float):
        if self.calls >= self.budget:
            self.last = {'status': 'budget', 'seconds': 0.0, 'content': None}
            raise BudgetExceeded()
        self.calls += 1
        status: Any = 'error'
        content = None
        started = time.perf_counter()
        try:
            response = self.inner(url, headers, body, timeout)
            status = 200
            try:
                content = response['choices'][0]['message']['content']
            except (KeyError, IndexError, TypeError):
                content = None
            return response
        except HTTPError as error:
            status = error.code
            raise
        except (TimeoutError, socket.timeout):
            status = 'timeout'
            raise
        except URLError as error:
            status = 'timeout' if isinstance(error.reason, (TimeoutError, socket.timeout)) else 'network'
            raise
        finally:
            self.last = {'status': status, 'seconds': round(time.perf_counter() - started, 2),
                         'content': content if type(content) is str else None}


def classify(content: Any, draft: Mapping[str, Any], supplemental: str,
             result: Mapping[str, Any]) -> dict[str, int]:
    """Count received/passed proposals and why each discarded one failed.

    ``passed`` is what enrich_notice actually accepted. The per-item reasons
    mirror its checks: quote (citation not verbatim on that page), value
    (values/text do not match a local candidate), kind (type outside
    RULE_TYPES) and json (unparseable response or wrong shape).
    """
    counts = {'received': 0, 'passed': len(result.get('suggestions', [])),
              'quote': 0, 'value': 0, 'kind': 0, 'json': 0, 'other': 0, 'screen_violation': 0}
    payload = notice_payload(draft, supplemental)
    counts['screen_violation'] = screen_violations(draft, payload, result)
    body = _object_json(content) if type(content) is str and len(content) <= MAX_RESPONSE else None
    if body is None or type(body.get('criteria')) is not list or 'guidance' not in body:
        counts['json'] += 1
        return counts
    whole_ok = _response(content) is not None
    reasons = []
    guide = body['guidance']
    if guide is not None:
        if type(guide) is not dict or set(guide) != {'text', 'page', 'quote'} or type(guide['text']) is not str:
            reasons.append('json')
        elif not _quote_valid(guide['page'], guide['quote'], payload):
            reasons.append('quote')
        elif not (4 <= len(guide['text'].strip()) <= 4000 and guide['text'].strip() in guide['quote']):
            reasons.append('value')
        else:
            reasons.append(None)
    for item in body['criteria']:
        if type(item) is not dict or set(item) != {'type', 'values_json', 'page', 'quote'}:
            reasons.append('json')
        elif item['type'] not in RULE_TYPES:
            reasons.append('kind')
        elif type(item['values_json']) is not str:
            reasons.append('json')
        elif not _quote_valid(item['page'], item['quote'], payload):
            reasons.append('quote')
        elif not _value_matches(item, draft):
            reasons.append('value')
        else:
            reasons.append(None)
    counts['received'] = len(reasons)
    for reason in reasons:
        if reason is not None:
            counts[reason] += 1
        elif not whole_ok:
            # A valid-looking item inside a body the local schema check rejected.
            counts['json'] += 1
    explained = counts['quote'] + counts['value'] + counts['kind'] + counts['json']
    counts['other'] = max(0, counts['received'] - counts['passed'] - explained)
    return counts


def _value_matches(item: Mapping[str, Any], draft: Mapping[str, Any]) -> bool:
    values = _object_json(item['values_json'])
    if values is None:
        return False
    for candidate in draft.get('criteria', []):
        quote = candidate.get('quote', '')
        if (candidate.get('type') == item['type'] and candidate.get('engine_rule')
                and candidate.get('page') == item['page'] and quote
                and (quote in item['quote'] or item['quote'] in quote)
                and _canonical(candidate.get('values')) == _canonical(values)):
            return True
    return False


def screen_violations(draft: Mapping[str, Any], payload: Mapping[str, Any], result: Mapping[str, Any]) -> int:
    """Accepted suggestions that would reach the screen without passing re-validation."""
    bad = int({key: value for key, value in result.items() if key != 'suggestions'} != dict(draft))
    candidates = {row.get('id'): row for row in draft.get('criteria', []) if isinstance(row, Mapping)}
    for row in result.get('suggestions', []):
        ok = (row.get('needs_review') is True and row.get('confidence') == 0.0
              and _quote_valid(row.get('page'), row.get('quote'), payload))
        if row.get('target_id') == 'guidance':
            ok = ok and type(row.get('text')) is str and row['text'] in row['quote']
        else:
            target = candidates.get(row.get('target_id'))
            ok = ok and target is not None and target.get('type') == row.get('type') \
                and _canonical(target.get('values')) == _canonical(row.get('values'))
        bad += not ok
    return bad


def _env(path: Path) -> dict[str, str]:
    from dotenv import dotenv_values
    values = {key: value or '' for key, value in dotenv_values(path).items()} if path.is_file() else {}
    return {**values, 'LLM_PROVIDER': 'jbai'}


def run_once(recorder: Recorder, provider: Any, notice: str, mode: str, phase: str, repeat: int,
             drafts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    recorder.last = {}
    draft = drafts[notice]
    supplemental = NOTICES[notice][1]
    # One mode per measurement: the provider's own format body, without its fallback.
    pinned = replace(provider, environ={**provider.environ, 'JBAI_RESPONSE_FORMAT': mode}, fallback=False)
    result = enrich_notice(draft, supplemental, provider=pinned)
    last = recorder.last or {'status': 'skipped', 'seconds': 0.0, 'content': None}
    content = last['content']
    parsed = _object_json(content) if type(content) is str else None
    row = {'phase': phase, 'mode': mode, 'notice': notice, 'repeat': repeat,
           'status': last['status'], 'seconds': last['seconds'],
           'json_ok': parsed is not None, 'schema_ok': _response(content) is not None}
    row.update(classify(content, draft, supplemental, result))
    row['discarded'] = row['received'] - row['passed']
    del content, parsed, last
    recorder.last = {}
    return row


def probe(*, environ: Mapping[str, str], transport: Callable[..., Mapping[str, Any]] = _http_transport,
          max_calls: int = 9, all_modes: bool = False, repeats: int = 2, mode: str | None = None) -> dict[str, Any]:
    budget = max(0, min(max_calls, HARD_CALL_LIMIT))
    recorder = Recorder(transport, budget)
    provider = configured_notice_provider(environ=environ, transport=recorder)
    if provider.name != 'jbai':
        return {'configured': False, 'calls': 0, 'mode': None, 'rows': []}
    drafts = {name: analyze_notice(public_pdf(pages), supplemental) for name, (pages, supplemental) in NOTICES.items()}
    rows: list[dict[str, Any]] = []
    chosen = mode
    if chosen is None:
        for candidate in MODES:
            row = run_once(recorder, provider, 'A', candidate, 'mode', 1, drafts)
            rows.append(row)
            if row['status'] == 200 and row['schema_ok'] and chosen is None:
                chosen = candidate
                if not all_modes:
                    break
            if row['status'] == 'budget':
                break
    if chosen is not None:
        for notice in NOTICES:
            for repeat in range(1, repeats + 1):
                rows.append(run_once(recorder, provider, notice, chosen, 'run', repeat, drafts))
    return {'configured': True, 'calls': recorder.calls, 'mode': chosen, 'rows': rows,
            'summary': summarize([row for row in rows if row['phase'] == 'run'])}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {}
    for notice in NOTICES:
        mine = [row for row in rows if row['notice'] == notice and row['status'] != 'budget']
        if not mine:
            continue
        summary[notice] = {
            'runs': len(mine),
            'avg_seconds': round(sum(row['seconds'] for row in mine) / len(mine), 2),
            'max_seconds': max(row['seconds'] for row in mine),
            'avg_received': round(sum(row['received'] for row in mine) / len(mine), 2),
            'avg_passed': round(sum(row['passed'] for row in mine) / len(mine), 2),
            'discarded': sum(row['discarded'] for row in mine),
            'screen_violation': sum(row['screen_violation'] for row in mine),
        }
    return summary


COLUMNS = (('phase', '구분'), ('mode', '모드'), ('notice', '공고문'), ('repeat', '회'), ('status', 'HTTP'),
           ('json_ok', 'JSON'), ('schema_ok', '스키마'), ('seconds', '초'), ('received', '제안'),
           ('passed', '통과'), ('discarded', '버림'), ('quote', '인용 불일치'), ('value', '값 불일치'),
           ('kind', '종류 밖'), ('json', 'JSON 오류'), ('screen_violation', '화면 위반'))


def table(report: Mapping[str, Any]) -> str:
    def cell(value: Any) -> str:
        return 'O' if value is True else 'X' if value is False else str(value)
    lines = ['| ' + ' | '.join(title for _, title in COLUMNS) + ' |',
             '|' + '---|' * len(COLUMNS)]
    for row in report['rows']:
        lines.append('| ' + ' | '.join(cell(row.get(key, '')) for key, _ in COLUMNS) + ' |')
    for notice, item in report.get('summary', {}).items():
        values = {'phase': '평균', 'mode': report['mode'], 'notice': notice, 'repeat': item['runs'],
                  'status': '-', 'json_ok': '-', 'schema_ok': '-',
                  'seconds': f"{item['avg_seconds']} (최대 {item['max_seconds']})",
                  'received': item['avg_received'], 'passed': item['avg_passed'],
                  'discarded': item['discarded'], 'quote': '-', 'value': '-', 'kind': '-', 'json': '-',
                  'screen_violation': item['screen_violation']}
        lines.append('| ' + ' | '.join(cell(values[key]) for key, _ in COLUMNS) + ' |')
    lines.append(f"| 호출 | {report['calls']} | 선택 모드 | {report['mode'] or '없음'} |" + ' |' * (len(COLUMNS) - 4))
    return '\n'.join(lines)


def main(argv: list[str] | None = None, *, transport: Callable[..., Mapping[str, Any]] = _http_transport) -> int:
    parser = argparse.ArgumentParser(description='JBAI notice suggestion probe (synthetic public notices only).')
    parser.add_argument('--json', action='store_true', help='print the same numbers as JSON')
    parser.add_argument('--all-modes', action='store_true', help='probe every format mode once')
    parser.add_argument('--mode', choices=MODES, help='skip mode probing and use this mode')
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--max-calls', type=int, default=9, help=f'real call budget (hard limit {HARD_CALL_LIMIT})')
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
    args = parser.parse_args(argv)
    try:
        report = probe(environ=_env(args.env_file), transport=transport, max_calls=args.max_calls,
                       all_modes=args.all_modes, repeats=max(1, args.repeats), mode=args.mode)
    except Exception:
        # Error objects may carry URLs, keys or bodies; print nothing from them.
        print('probe failed')
        return 1
    if not report['configured']:
        print('JBAI 설정 없음 또는 안전하지 않음 (LLM 호출 0회)')
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else table(report))
    return 0 if report['mode'] else 1


if __name__ == '__main__':
    sys.exit(main())
