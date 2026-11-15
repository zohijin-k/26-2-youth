"""Bind confirmed generic criteria to existing rules, never to AI decisions."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date
import math
from typing import Any

from engine_v2.pipeline.privacy import mask_data
from engine_v2.rules.registry import RuleContext, current_sido_is, settings_issue_date
from engine_v2.schemas.models import ApplicantInput, CheckStatus, DocType as EngineDocType, ExtractedField, FieldSource

from .engine_adapter import engine_config, to_engine_documents
from .models import Application, Document
from .notice_analysis import SUPPORTED_RULES
from .rules.age_eligibility import assess_age
from .rules.doc_types import DocType
from .rules.facts import build_facts, parse_ymd
from .rules.identity import compare, identity_of
from .rules.programs import get_program
from .rules.required_docs import WorkCategory
from .rules.scoring import score_income
from .rules.work_continuity import _complete, _date as rule_date, assess_work

_STATUS = {CheckStatus.PASS: 'PASS', CheckStatus.FAIL: 'FAIL', CheckStatus.UNKNOWN: 'NEEDS_REVIEW'}


def _result(candidate: dict[str, Any], status: str = 'NEEDS_REVIEW',
            basis: str = '원본과 사업 기준을 담당자가 확인해야 합니다.',
            identifiers: list[int] | None = None, *, blockable: bool = False) -> dict[str, Any]:
    return {'id': candidate.get('id'), 'type': candidate.get('type', 'checklist'),
            'status': status, 'result': status, 'basis': basis,
            'source_document_ids': list(dict.fromkeys(identifiers or [])),
            'submission_blocking': status == 'FAIL' and blockable}


def _facts(documents: list[Document | dict[str, Any]]) -> list[dict[str, Any]]:
    from .api.common import document_fact
    return [document_fact(row) if isinstance(row, Document) else deepcopy(row) for row in documents]


def _confidence(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1


def _trusted(rows: list[dict[str, Any]], identity: Any) -> list[dict[str, Any]]:
    """Reuse the existing engine conversion's confidence/failure safety filter."""
    if identity is None:
        return []
    result = []
    eligible = [row for row in rows if isinstance(row, dict)
                and _confidence(row.get('confidence')) and _confidence(row.get('image_quality'))]
    if not eligible:
        return result
    try:
        converted = to_engine_documents(eligible)
    except (ValueError, TypeError, OverflowError):
        return []
    for row, document in zip(eligible, converted):
        fields = row.get('fields') or {}
        if (not isinstance(fields, dict) or row.get('status') != 'PASS'
                or not _confidence(document.ocr_confidence) or not _confidence(document.image_quality_score)
                or document.ocr_confidence < engine_config.OCR_CONFIDENCE_THRESHOLD
                or document.image_quality_score < engine_config.IMAGE_QUALITY_THRESHOLD
                or document.is_encrypted_or_corrupted or not _complete(fields)
                or fields.get('판독검증실패')):
            continue
        checked, mismatched = compare(identity, fields)
        if set(checked) != {'성명', '생년월일'} or mismatched:
            continue
        clean = deepcopy(row)
        clean['confidence'] = document.ocr_confidence
        result.append(clean)
    return result


def _context(app: Application, identity: Any, basis: date, *, fields: dict[str, Any], criteria: dict[str, Any] | None = None) -> RuleContext:
    return RuleContext(reference_date=basis,
        applicant=ApplicantInput(name=identity.name, birth_date=identity.birth), declared_values={},
        detected_type=EngineDocType.RESIDENT_ABSTRACT,
        fields={key: ExtractedField(value=value, raw_text='', confidence=1, source=FieldSource.TEXT_LAYER)
                for key, value in fields.items()},
        application_date=(app.submitted_at or app.created_at).date(), criteria=criteria or {})


def _residence(app: Application, candidate: dict[str, Any], trusted: list[dict[str, Any]], identity: Any) -> dict[str, Any]:
    from engine_v2.extractors.resident_abstract import SIDO
    values = candidate['values']
    if values.get('city'):
        return _result(candidate)
    basis = parse_ymd(values.get('basis_date'))
    if basis is None:
        return _result(candidate)
    wanted = SIDO.get(values.get('province'), values.get('province'))
    outcomes = []
    identifiers = []
    for row in trusted:
        if row.get('doc_type') != str(DocType.RESIDENT_ABSTRACT):
            continue
        fields = row['fields']
        issue = rule_date(row.get('issue_date')) or parse_ymd(fields.get('발급일'))
        start = parse_ymd(fields.get('전입일'))
        current = fields.get('현주소시도')
        # A later current address alone does not prove residence on an earlier
        # notice date. The existing extractor's continuous-residence start and
        # a document issued on/after that date must both be present.
        if issue is None or issue < basis or start is None or start > basis or not current or current == '판별불가':
            continue
        context = _context(app, identity, basis, fields={'address_history': [{'sido': SIDO.get(current, current)}]})
        status, _ = current_sido_is(context, {'sido': wanted})
        outcomes.append(_STATUS[status])
        if row.get('document_id'):
            identifiers.append(row['document_id'])
    if not outcomes or len(set(outcomes)) != 1:
        return _result(candidate, identifiers=identifiers)
    return _result(candidate, outcomes[0], f'기존 시도 거주 규칙 · 기준일 {basis.isoformat()} · {values["province"]}', identifiers)


def _issue(app: Application, candidate: dict[str, Any], trusted: list[dict[str, Any]], identity: Any,
           all_rows: list[dict[str, Any]]) -> dict[str, Any]:
    from .api.program_analysis import issue_scope_supported
    values = candidate['values']
    cutoff = parse_ymd(values.get('date'))
    if cutoff is None or values.get('mode') != 'after_date' or not all_rows or not issue_scope_supported(candidate.get('quote', '')):
        return _result(candidate)
    statuses = []
    identifiers = []
    for row in trusted:
        issue = rule_date(row.get('issue_date')) or parse_ymd(row['fields'].get('발급일'))
        if issue is None:
            continue
        context = _context(app, identity, cutoff, fields={'issue_date': issue},
            criteria={'document_issue_fallback': {'mode': 'after_date', 'date': cutoff.isoformat()}})
        status, _ = settings_issue_date(context, {'field': 'issue_date'})
        statuses.append(_STATUS[status])
        if row.get('document_id'):
            identifiers.append(row['document_id'])
    # Certain failure is useful even if another document is unreadable; a pass
    # requires every uploaded document to provide trusted issue-date evidence.
    if 'FAIL' in statuses:
        return _result(candidate, 'FAIL', f'기존 발급일 규칙 · {cutoff.isoformat()} 이후 발급분', identifiers, blockable=True)
    status = 'PASS' if len(statuses) == len(all_rows) and statuses else 'NEEDS_REVIEW'
    return _result(candidate, status, f'기존 발급일 규칙 · {cutoff.isoformat()} 이후 발급분', identifiers)


def _work(app: Application, candidate: dict[str, Any], trusted: list[dict[str, Any]], identity: Any) -> dict[str, Any]:
    values = candidate['values']
    basis = parse_ymd(values.get('basis_date'))
    months = values.get('months')
    if basis is None or type(months) is not int or not 1 <= months <= 120:
        return _result(candidate)
    program = replace(get_program('job_package'), has_work_requirement=True, work_continuity_months=months)
    kinds = {row.get('doc_type') for row in trusted}
    employee = bool(kinds & {str(DocType.INSURANCE_4), str(DocType.DAILY_WORK_RECORD), str(DocType.NHIS_ACQUISITION_LOSS)})
    business = str(DocType.BIZ_REG_PROOF) in kinds
    # Existing work-category-specific rules determine whether the evidence
    # covers the duration. Conflicting categories remain for officer review.
    category = WorkCategory.EMPLOYEE if employee and not business else WorkCategory.BUSINESS if business and not employee else None
    result = assess_work(program, basis, category, trusted, identity)
    ids = [row['document_id'] for row in result.evidence if row.get('document_id')]
    return _result(candidate, result.review_status, result.basis, ids, blockable=True)


def _income(candidate: dict[str, Any], trusted: list[dict[str, Any]]) -> dict[str, Any]:
    from .api.program_analysis import _income_supported
    values = candidate['values']
    months = values.get('premium_months')
    if not _income_supported(values) or not isinstance(months, list) or not months:
        return _result(candidate, basis='소득 기준표와 심사 대상 고지 월을 담당자가 확인해야 합니다.')
    result = score_income(build_facts({}, trusted, months))
    status = {'MET': 'PASS', 'OVER_LIMIT': 'FAIL'}.get(result.status, 'NEEDS_REVIEW')
    ids = [row['document_id'] for row in trusted
           if row.get('doc_type') in {str(DocType.NHIS_PAYMENT), str(DocType.NHIS_QUALIFICATION)} and row.get('document_id')]
    return _result(candidate, status, result.item.basis, ids, blockable=True)


def evaluate(app: Application, criteria: list[dict[str, Any]],
             documents: list[Document | dict[str, Any]]) -> list[dict[str, Any]]:
    rows = _facts(documents)
    identity = identity_of(app.identity_json)
    trusted = _trusted(rows, identity)
    results = []
    for candidate in criteria:
        kind = candidate.get('type')
        if (candidate.get('needs_review', True) or kind not in SUPPORTED_RULES
                or candidate.get('engine_rule') != SUPPORTED_RULES[kind]
                or not isinstance(candidate.get('values'), dict) or identity is None):
            results.append(_result(candidate))
            continue
        try:
            if kind == 'age':
                values = candidate['values']
                low, high = parse_ymd(values.get('birth_start')), parse_ymd(values.get('birth_end'))
                if low is None or high is None or low > high:
                    result = _result(candidate)
                else:
                    program = replace(get_program('job_package'), birth_range=(low, high))
                    age = assess_age(program, identity.birth.isoformat(), app.identity_json)
                    ids = [row['document_id'] for row in trusted if row.get('doc_type') == str(DocType.RESIDENT_ABSTRACT) and row.get('document_id')]
                    result = _result(candidate, age.status, '본인확인 정보 · ' + age.basis, ids, blockable=True)
            elif kind == 'residence':
                result = _residence(app, candidate, trusted, identity)
            elif kind == 'issue_date':
                result = _issue(app, candidate, trusted, identity, rows)
            elif kind == 'work_continuity':
                result = _work(app, candidate, trusted, identity)
            else:
                result = _income(candidate, trusted)
        except (ValueError, TypeError, KeyError, OverflowError):
            result = _result(candidate)
        results.append(result)
    return mask_data(results)


def applicant_blockers(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """An allowlist excludes checklist, evidence, quotes and confidence entirely."""
    labels = {'age': '연령 요건', 'issue_date': '서류 발급일 요건', 'income': '소득 요건', 'work_continuity': '근로 계속성 요건'}
    output = []
    for result in results:
        kind = result.get('type')
        if kind not in labels or result.get('status') != 'FAIL' or not result.get('submission_blocking'):
            continue
        label = labels[kind]
        output.append({'kind': 'eligibility', 'target': 'identity' if kind == 'age' else 'upload',
            'label': label, 'code': 'PROGRAM_REQUIREMENT_NOT_MET',
            'message': f'공고문의 {label}과 일치하지 않습니다. 입력 정보와 원본을 확인해 주세요.',
            'goto': 'identity' if kind == 'age' else 'upload'})
    return output
