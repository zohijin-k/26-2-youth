"""One-shot public program uploads and strictly reviewed notice metadata."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date, datetime
from io import BytesIO
import json
import math
import re
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict

from engine_v2.pipeline.privacy import mask_data
from ..models import ProgramPosting, get_session, session_transaction
from ..notice_analysis import SUPPORTED_RULES, analyze_notice
from ..rules.doc_types import DocType
from ..rules.required_docs import DocRequirement
from . import postings, posting_workspace as workspace

router = APIRouter(prefix='/api/officer', tags=['program notice analysis'])
_IDENTIFIER = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,79}\Z')
_DAY = re.compile(r'\d{4}-\d{2}-\d{2}\Z')
_KINDS = set(SUPPORTED_RULES) | {'checklist'}
_VALUE_KEYS = {'birth_start', 'birth_end', 'basis_date', 'min_age', 'max_age',
               'province', 'city', 'mode', 'date', 'months', 'percent', 'operator',
               'household_table', 'premium_months', 'text'}
_PROVINCES = {'전북특별자치도', '전라북도', '전북', '전라남도', '경상북도', '경상남도',
              '충청북도', '충청남도', '강원특별자치도', '강원도', '경기도', '제주특별자치도',
              '서울특별시', '부산광역시', '대구광역시', '인천광역시', '광주광역시',
              '대전광역시', '울산광역시', '세종특별자치시'}


def posting_is_v2(posting: ProgramPosting) -> bool:
    return (posting.template_json or {}).get('authoring_version') == 2


def analysis_of(posting: ProgramPosting) -> dict[str, Any] | None:
    value = (posting.template_json or {}).get('notice_draft')
    return deepcopy(value) if posting_is_v2(posting) and isinstance(value, dict) else None


def _invalid() -> None:
    raise HTTPException(422, '사업 초안의 항목·근거·종류·값을 확인해 주세요.')


def _text(value: Any, maximum: int, *, empty: bool = False) -> str:
    if type(value) is not str or len(value) > maximum or (not empty and not value.strip()):
        _invalid()
    return mask_data(value.strip())


def _date(value: Any, *, empty: bool = False) -> str:
    if empty and value in ('', None):
        return ''
    if type(value) is not str or not _DAY.fullmatch(value):
        _invalid()
    try:
        date.fromisoformat(value)
    except ValueError:
        _invalid()
    return value


def _candidate(raw: Any, trusted: dict[str, Any], known_ids: set[str]) -> dict[str, Any]:
    if type(raw) is not dict:
        _invalid()
    identifier = raw.get('id')
    if type(identifier) is not str or not _IDENTIFIER.fullmatch(identifier):
        _invalid()
    if identifier not in known_ids and not identifier.startswith('manual_'):
        _invalid()
    review = raw.get('needs_review')
    confidence = raw.get('confidence', 0)
    if type(review) is not bool or type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
        _invalid()
    quote = _text(raw.get('quote', ''), 240, empty=True)
    page = raw.get('page')
    if page is None:
        if quote:
            if quote not in trusted.get('supplemental', ''):
                _invalid()
            source = 'supplemental'
        else:
            source = 'manual'
    else:
        if type(page) is not int or not quote or not any(row['page'] == page and quote in row['text'] for row in trusted['source_pages']):
            _invalid()
        source = 'notice'
    return {'id': identifier, 'page': page, 'quote': quote, 'source': source,
            'confidence': float(confidence) if source != 'manual' else 0.0,
            'needs_review': review}


def _income_supported(values: dict[str, Any]) -> bool:
    from ..rules.scoring import MEDIAN_INCOME_140
    raw = values.get('household_table')
    if type(raw) is not dict:
        return False
    try:
        table = {int(key): value for key, value in raw.items()}
    except (ValueError, TypeError):
        return False
    return values.get('percent') == 140 and values.get('operator') == '이하' and table == MEDIAN_INCOME_140


def issue_scope_supported(quote: str) -> bool:
    """A document-family cutoff cannot become a global cutoff by inference."""
    return not re.search(r'초본|등본|통장|건강보험|4대보험|영수증|증명서|확인서|서류별|해당\s*서류|특정\s*서류', quote)


def _values(kind: str, raw: Any, automatic: bool, *, pending: bool = False) -> tuple[str, dict[str, Any], bool]:
    if type(raw) is not dict or set(raw) - _VALUE_KEYS:
        _invalid()
    allowed = {
        'age': {'birth_start', 'birth_end', 'basis_date', 'min_age', 'max_age'},
        'residence': {'province', 'city', 'basis_date'},
        'issue_date': {'mode', 'date', 'basis_date'},
        'work_continuity': {'months', 'basis_date'},
        'income': {'percent', 'operator', 'household_table', 'premium_months'},
    }
    if automatic and set(raw) - allowed[kind]:
        _invalid()
    try:
        encoded = json.dumps(raw, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        _invalid()
    if len(encoded) > 20_000:
        _invalid()
    value = mask_data(deepcopy(raw))
    for key in ('birth_start', 'birth_end', 'basis_date', 'date'):
        if key in value:
            value[key] = _date(value[key], empty=not automatic or pending or (kind == 'age' and key == 'basis_date'))
    for key in ('min_age', 'max_age', 'months'):
        if key in value and value[key] is not None:
            if type(value[key]) is not int or not 0 <= value[key] <= 120:
                _invalid()
    for key in ('province', 'city', 'mode', 'operator', 'text'):
        if key in value:
            value[key] = _text(value[key], 2000 if key == 'text' else 100, empty=True)
    if 'percent' in value and (type(value['percent']) not in (int, float) or not math.isfinite(value['percent']) or not 0 < value['percent'] <= 1000):
        _invalid()
    if 'premium_months' in value:
        months = value['premium_months']
        if type(months) is not list or not 1 <= len(months) <= 12:
            _invalid()
        for month in months:
            if type(month) is not str or not re.fullmatch(r'\d{4}-\d{2}', month):
                _invalid()
            _date(month + '-01')
        value['premium_months'] = list(dict.fromkeys(months))
    if not automatic:
        return 'checklist', value, False
    if kind == 'age':
        if not value.get('birth_start') or not value.get('birth_end') or value['birth_start'] > value['birth_end']:
            if pending:
                return kind, value, False
            _invalid()
    elif kind == 'residence':
        if value.get('province') not in _PROVINCES or not value.get('basis_date'):
            if pending:
                return kind, value, False
            _invalid()
        if value.get('city'):
            return 'checklist', value, False
    elif kind == 'issue_date':
        if value.get('mode') != 'after_date' or not value.get('date'):
            if pending:
                return kind, value, False
            _invalid()
    elif kind == 'work_continuity':
        if not value.get('months') or not value.get('basis_date'):
            if pending:
                return kind, value, False
            _invalid()
    elif kind == 'income':
        if not _income_supported(value):
            if pending:
                return kind, value, False
            return 'checklist', value, False
    return kind, value, True


def validate_analysis(raw: Any, stored: dict[str, Any], supplemental: str = '') -> dict[str, Any]:
    """Only stored public source text establishes citations; manual work has none."""
    if type(raw) is not dict or set(raw) - {'version', 'status', 'title', 'period', 'guidance', 'required_docs', 'criteria', 'source_pages', 'warnings', 'suggestions'}:
        _invalid()
    if raw.get('version') != 1:
        _invalid()
    pages = stored.get('source_pages', [])
    if 'source_pages' in raw and raw['source_pages'] != pages:
        _invalid()
    trusted = {'source_pages': pages, 'supplemental': supplemental}
    originals = [stored.get(name, {}) for name in ('title', 'period', 'guidance')]
    originals.extend(stored.get('required_docs', []))
    originals.extend(stored.get('criteria', []))
    known = {row.get('id') for row in originals if isinstance(row, dict)}
    for row in originals:
        if not isinstance(row, dict):
            continue
        if isinstance(row.get('basis_evidence'), dict):
            known.add(row['basis_evidence'].get('id'))
        for name in ('sources', 'table_evidence'):
            for evidence in row.get(name, []):
                if isinstance(evidence, dict):
                    known.add(evidence.get('id'))
    def citation(raw_evidence: Any, reviewed: bool) -> dict[str, Any]:
        if type(raw_evidence) is not dict or set(raw_evidence) - {'id', 'value', 'page', 'quote', 'source', 'confidence', 'needs_review'}:
            _invalid()
        clean_evidence = _candidate(raw_evidence, trusted, known)
        try:
            encoded = json.dumps(raw_evidence.get('value'), ensure_ascii=False, allow_nan=False)
        except (ValueError, TypeError):
            _invalid()
        if len(encoded) > 4000:
            _invalid()
        clean_evidence['value'] = mask_data(deepcopy(raw_evidence.get('value')))
        clean_evidence['needs_review'] = reviewed
        return clean_evidence
    output = {'version': 1, 'status': stored.get('status', 'draft'), 'source_pages': deepcopy(pages),
              'warnings': deepcopy(stored.get('warnings', []))}
    allowed_basic = {'id', 'value', 'page', 'quote', 'source', 'confidence', 'needs_review', 'sources'}
    for name, limit in (('title', 100), ('period', 0), ('guidance', postings.GUIDANCE_MAX)):
        item = raw.get(name)
        if type(item) is not dict or set(item) - allowed_basic or item.get('id') != name:
            _invalid()
        clean = _candidate(item, trusted, known)
        if name == 'period':
            values = item.get('value')
            if type(values) is not dict or set(values) != {'apply_start', 'apply_end'}:
                _invalid()
            clean['value'] = {key: _date(value, empty=True) for key, value in values.items()}
        else:
            clean['value'] = _text(item.get('value'), limit, empty=True)
        if item.get('sources'):
            if type(item['sources']) is not list or len(item['sources']) > 100:
                _invalid()
            clean['sources'] = [citation(evidence, clean['needs_review']) for evidence in item['sources']]
        output[name] = clean
    for name in ('required_docs', 'criteria'):
        if type(raw.get(name)) is not list or len(raw[name]) > 100:
            _invalid()
        output[name] = []
    catalog = workspace.slot_catalog()
    for item in raw['required_docs']:
        allowed = {'id', 'type', 'slot_key', 'label', 'original_label', 'required', 'review_reason', 'page', 'quote', 'source', 'confidence', 'needs_review'}
        if type(item) is not dict or set(item) - allowed or item.get('type') != 'document' or type(item.get('required')) is not bool:
            _invalid()
        clean = _candidate(item, trusted, known)
        slot = item.get('slot_key')
        if slot is not None and (type(slot) is not str or slot not in catalog):
            _invalid()
        clean.update(type='document', slot_key=slot, label=_text(item.get('label'), 200), required=item['required'])
        if slot is None:
            clean.update(label='기타 서류', original_label=_text(item.get('original_label') or item.get('label'), 200))
        output['required_docs'].append(clean)
    known_slots = [item['slot_key'] for item in output['required_docs'] if item['slot_key']]
    if len(set(known_slots)) != len(known_slots):
        _invalid()
    for item in raw['criteria']:
        allowed = {'id', 'type', 'candidate_type', 'label', 'values', 'engine_rule', 'review_reason', 'basis_evidence', 'table_evidence', 'page', 'quote', 'source', 'confidence', 'needs_review'}
        if type(item) is not dict or set(item) - allowed or item.get('type') not in _KINDS:
            _invalid()
        clean = _candidate(item, trusted, known)
        candidate_kind = item.get('candidate_type', item['type'])
        if candidate_kind not in _KINDS:
            _invalid()
        kind, values, bound = _values(item['type'], item.get('values'), item['type'] != 'checklist', pending=clean['needs_review'])
        if kind == 'issue_date' and not issue_scope_supported(clean['quote']):
            kind, bound = 'checklist', False
        engine = SUPPORTED_RULES.get(kind) if bound else None
        if item.get('engine_rule') not in (None, engine, SUPPORTED_RULES.get(item['type'])):
            _invalid()
        clean.update(type=kind, candidate_type=candidate_kind, label=_text(item.get('label'), 240), values=values, engine_rule=engine)
        if item.get('review_reason'):
            clean['review_reason'] = _text(item['review_reason'], 1000)
        if item.get('basis_evidence'):
            clean['basis_evidence'] = citation(item['basis_evidence'], clean['needs_review'])
        if item.get('table_evidence'):
            if type(item['table_evidence']) is not list or len(item['table_evidence']) > 100:
                _invalid()
            clean['table_evidence'] = [citation(evidence, clean['needs_review']) for evidence in item['table_evidence']]
        output['criteria'].append(clean)
    identifiers = [output[name]['id'] for name in ('title', 'period', 'guidance')]
    identifiers += [item['id'] for name in ('required_docs', 'criteria') for item in output[name]]
    if len(set(identifiers)) != len(identifiers):
        _invalid()
    return output


def analysis_blockers(posting: ProgramPosting) -> list[str]:
    if not posting_is_v2(posting):
        return []
    draft = analysis_of(posting)
    if not draft:
        return ['공고문 분석 초안을 확인해 주세요.']
    problems = []
    basics = [draft.get(name, {}) for name in ('title', 'period', 'guidance')]
    if not basics[0].get('value', '').strip():
        problems.append('사업 제목을 입력해 주세요.')
    if not basics[2].get('value', '').strip():
        problems.append('안내문을 입력해 주세요.')
    period = basics[1].get('value') or {}
    start, end = period.get('apply_start', ''), period.get('apply_end', '')
    if not start or not end or start > end or end < postings._today().isoformat():
        problems.append('신청 기간이 유효하지 않습니다.')
    if not draft.get('required_docs') or not draft.get('criteria'):
        problems.append('제출 서류와 기준을 하나 이상 입력해 주세요.')
    candidates = basics + draft.get('required_docs', []) + draft.get('criteria', [])
    pending = sum(item.get('needs_review', True) is not False for item in candidates)
    if pending:
        problems.append(f'확인할 항목 {pending}개를 모두 확인해 주세요.')
    if (posting.title != basics[0].get('value') or posting.guidance_text != basics[2].get('value')
            or posting.apply_start.isoformat() != start or posting.apply_end.isoformat() != end):
        problems.append('예시 페이지의 사업 정보를 저장해 주세요.')
    expected = list(dict.fromkeys(item['slot_key'] for item in draft.get('required_docs', []) if item.get('slot_key')))
    if (posting.template_json or {}).get('required_docs', []) != expected:
        problems.append('제출 서류 설정을 예시 페이지에서 다시 저장해 주세요.')
    return problems


def freeze_requirements(posting: ProgramPosting, catalog: dict[str, DocRequirement]) -> list[dict[str, Any]] | None:
    """Officer-only evidence is kept out of these applicant-visible requirements."""
    draft = analysis_of(posting)
    if draft is None:
        return None
    result = []
    for item in draft['required_docs']:
        if item['slot_key']:
            req = replace(catalog[item['slot_key']], required=item['required'], label=item['label'])
        else:
            # The shared enum gains this additive member at integration. Unknown
            # uploads always require officer review, even if a reader finds text.
            req = DocRequirement(slot_key='other_' + item['id'], doc_type=DocType('기타서류'),
                label=item.get('original_label') or '기타 서류', required=item['required'],
                check_declared_date=False, date_basis='none',
                notes=['담당자가 원본을 확인하는 서류입니다.'])
        result.append(asdict(req))
    return result


def snapshot_metadata(posting: ProgramPosting) -> dict[str, Any]:
    draft = analysis_of(posting)
    return {'authoring_version': 2, 'criteria': deepcopy(draft['criteria'])} if draft else {}


def _view(posting: ProgramPosting) -> dict[str, Any]:
    return {**workspace.view(posting), 'analysis': analysis_of(posting), 'authoring_version': 2 if posting_is_v2(posting) else 1}


@router.post('/programs/analyze', status_code=201)
def upload_and_analyze(notice_pdf: UploadFile = File(...), forms_pdfs: list[UploadFile] = File(...),
                       supplemental: str = Form('', max_length=4000)) -> dict[str, Any]:
    if not 1 <= len(forms_pdfs) <= 10:
        raise HTTPException(422, '서식 PDF는 1~10개 올려 주세요.')
    notice, notice_name = postings._read_pdf(notice_pdf, 'notice')
    form_files = [postings._read_pdf(upload, 'forms') for upload in forms_pdfs]
    try:
        draft = analyze_notice(notice, supplemental)
    except ValueError:
        raise HTTPException(422, '공고문 PDF와 부가 설명문을 확인해 주세요.') from None
    period = draft['period']['value']
    today = postings._today().isoformat()
    start, end = period['apply_start'] or today, period['apply_end'] or today
    if start > end:
        start = end = today
    slots = list(dict.fromkeys(item['slot_key'] for item in draft['required_docs'] if item.get('slot_key')))
    uploads = [UploadFile(file=BytesIO(data), filename=name) for data, name in form_files]
    with session_transaction():
        created = postings.create_posting(title=draft['title']['value'] or '작성 중 사업', apply_start=start,
            apply_end=end, notice_pdf=UploadFile(file=BytesIO(notice), filename=notice_name),
            forms_pdf=uploads[0], forms_pdfs=uploads[1:], workflow_version=1,
            required_docs=json.dumps(slots), guidance_text=draft['guidance']['value'])
        with get_session() as session:
            posting = postings._find(session, created['id'])
            posting.template_json = {**posting.template_json, 'authoring_version': 2,
                                     'notice_draft': draft, 'public_supplemental': supplemental}
            session.add(posting)
            session.commit()
    return _view(postings._load(created['id']))


class AnalysisEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    analysis: dict[str, Any]


def legacy_analysis(posting: ProgramPosting) -> dict[str, Any]:
    """Opt in an old managed draft without inventing source quotations."""
    def manual(identifier: str, value: Any) -> dict[str, Any]:
        return {'id': identifier, 'value': value, 'page': None, 'quote': '', 'source': 'manual',
                'confidence': 0, 'needs_review': True}
    catalog = workspace.slot_catalog()
    docs = []
    for slot in (posting.template_json or {}).get('required_docs', []):
        row = manual('manual_document_' + slot, None)
        row.pop('value')
        row.update(type='document', slot_key=slot, label=catalog[slot].label, required=True)
        docs.append(row)
    return {'version': 1, 'status': 'draft', 'title': manual('title', posting.title),
            'period': manual('period', {'apply_start': posting.apply_start.isoformat(), 'apply_end': posting.apply_end.isoformat()}),
            'guidance': manual('guidance', posting.guidance_text), 'required_docs': docs,
            'criteria': [], 'source_pages': [], 'warnings': []}


@router.put('/postings/{posting_id}/analysis')
def update_analysis(posting_id: int, body: AnalysisEdit) -> dict[str, Any]:
    with get_session() as session:
        posting = postings._find(session, posting_id)
        workspace.editable(posting)
        stored = analysis_of(posting)
        if stored is None:
            stored = legacy_analysis(posting)
        clean = validate_analysis(body.analysis, stored, (posting.template_json or {}).get('public_supplemental', ''))
        posting.title = clean['title']['value'] or '작성 중 사업'
        posting.guidance_text = clean['guidance']['value']
        period = clean['period']['value']
        if period['apply_start']:
            posting.apply_start = date.fromisoformat(period['apply_start'])
        if period['apply_end']:
            posting.apply_end = date.fromisoformat(period['apply_end'])
        posting.template_json = {**posting.template_json, 'authoring_version': 2, 'notice_draft': clean,
            'required_docs': list(dict.fromkeys(item['slot_key'] for item in clean['required_docs'] if item.get('slot_key')))}
        posting.updated_at = datetime.now()
        session.add(posting)
        session.commit()
        session.refresh(posting)
    return _view(posting)
