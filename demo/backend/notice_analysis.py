"""Evidence-backed public-notice drafts, without eligibility decisions.

This module reads public PDF text locally. Every suggestion remains unconfirmed.
Only an existing rule function can be a binding; unsupported conditions remain
officer checklists. There is deliberately no OCR/network fallback here: an image
notice is returned for manual entry rather than guessed or sent to a provider.
"""
from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256
import re
from typing import Any

import pymupdf

from .forms.draft import draft_layout

SUPPORTED_RULES = {
    'age': 'demo.backend.rules.age_eligibility.assess_age',
    'residence': 'engine_v2.rules.registry.current_sido_is',
    'issue_date': 'engine_v2.rules.registry.settings_issue_date',
    'income': 'demo.backend.rules.scoring.score_income',
    'work_continuity': 'demo.backend.rules.work_continuity.assess_work',
}
MAX_SUPPLEMENTAL = 4000
MAX_NOTICE_TEXT = 200_000
_DATE = re.compile(r'(?<!\d)(20\d{2}|19\d{2})\s*[.년/-]\s*(\d{1,2})\s*[.월/-]\s*(\d{1,2})\s*일?\.?')
_SHORT_DATE = re.compile(r'(?<!\d)(\d{1,2})\s*[.월/-]\s*(\d{1,2})\s*일?\.?')
_AGE = re.compile(r'(?:만\s*)?(\d{1,2})\s*세?\s*(?:이상\s*[-~∼～]?\s*|[-~∼～]\s*)(?:만\s*)?(\d{1,2})\s*세\s*(?:이하)?')
_PROVINCE = re.compile(r'(전북특별자치도|전라북도|전북|전남특별자치도|전라남도|경상북도|경상남도|충청북도|충청남도|강원특별자치도|강원도|경기도|제주특별자치도|서울특별시|부산광역시|대구광역시|인천광역시|광주광역시|대전광역시|울산광역시|세종특별자치시)')
_CITY = re.compile(r'(?:전북특별자치도|전라북도|전북)?\s*(전주시|군산시|익산시|정읍시|남원시|김제시|완주군|진안군|무주군|장수군|임실군|순창군|고창군|부안군)')
_DOC_ALIASES = {
    'resident_abstract': ('주민등록초본', '주민등록표 초본', '주민등록표초본'),
    'nhis_payment': ('건강보험료 납부확인서', '건강보험료납부확인서'),
    'nhis_qualification': ('건강보험 자격확인서', '건강보험자격확인서'),
    'nhis_acquisition_loss': ('건강보험 자격득실확인서', '건강보험자격득실확인서'),
    'bank_account': ('통장 사본', '통장사본'),
    'work_proof_1': ('4대보험 가입내역확인서', '4대보험가입내역확인서'),
}


def _day(match: re.Match[str]) -> date | None:
    try:
        return date(*(int(value) for value in match.groups()))
    except ValueError:
        return None


def _dates(text: str) -> list[date]:
    return [value for match in _DATE.finditer(text) if (value := _day(match)) is not None]


def _evidence(identifier: str, value: Any, line: dict[str, Any] | None,
              confidence: float = .7) -> dict[str, Any]:
    return {'id': identifier, 'value': value, 'page': line['page'] if line else None,
            'quote': line['text'][:240] if line else '',
            'source': line['source'] if line else 'manual',
            'confidence': confidence if line else 0.0, 'needs_review': True}


def _id(kind: str, line: dict[str, Any]) -> str:
    key = f'{kind}:{line["page"]}:{line["text"]}'
    return kind + '_' + sha256(key.encode()).hexdigest()[:12]


def _criterion(kind: str, line: dict[str, Any], values: dict[str, Any], *,
               supported: bool = True, reason: str = '') -> dict[str, Any]:
    candidate = _evidence(_id(kind, line), values, line)
    # Criteria use ``values`` consistently with the officer editor. Evidence is
    # at candidate level; individual configuration values never lose its source.
    candidate['values'] = candidate.pop('value')
    candidate.update(type=kind if supported else 'checklist', candidate_type=kind,
                     label=line['text'][:240],
                     engine_rule=SUPPORTED_RULES.get(kind) if supported else None)
    if reason:
        candidate['review_reason'] = reason
    return candidate


def notice_pages(pdf: bytes) -> list[dict[str, Any]]:
    """Bounded text extraction; failures never retain provider/raw exceptions."""
    try:
        with pymupdf.open(stream=pdf, filetype='pdf') as document:
            if document.is_encrypted or not 0 < document.page_count <= 100:
                raise ValueError('notice is unavailable')
            pages = []
            remaining = MAX_NOTICE_TEXT
            for number, page in enumerate(document, start=1):
                text = page.get_text(sort=True)[:remaining]
                remaining -= len(text)
                pages.append({'page': number, 'text': text})
                if remaining <= 0:
                    break
            return pages
    except Exception:
        raise ValueError('공고문 PDF를 읽을 수 없습니다. 암호가 없는 정상 PDF를 올려 주세요.') from None


def _lines(pages: list[dict[str, Any]], supplemental: str) -> list[dict[str, Any]]:
    lines = [{'page': page['page'], 'text': line.strip(), 'source': 'notice'}
             for page in pages for line in page['text'].splitlines() if line.strip()]
    lines.extend({'page': None, 'text': line.strip(), 'source': 'supplemental'}
                 for line in supplemental.splitlines() if line.strip())
    return lines


def _period_candidates(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for index, line in enumerate(lines):
        if not re.search(r'(신청|접수|모집)\s*기간', line['text']):
            continue
        nearby = [row for row in lines[index:index + 3]
                  if row['page'] == line['page'] and row['source'] == line['source']]
        for row in nearby:
            dates = _dates(row['text'])
            if len(dates) == 1:
                end = _SHORT_DATE.search(_DATE.sub('', row['text']))
                if end:
                    try:
                        dates.append(date(dates[0].year, int(end[1]), int(end[2])))
                    except ValueError:
                        pass
            if len(dates) == 2 and dates[0] <= dates[1]:
                result.append(_evidence('period', {'apply_start': dates[0].isoformat(),
                    'apply_end': dates[1].isoformat()}, row, .85))
    return list({tuple(item['value'].values()): item for item in result}.values())


def _period(lines: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = _period_candidates(lines)
    if len(candidates) == 1:
        return candidates[0]
    empty = _evidence('period', {'apply_start': '', 'apply_end': ''}, None)
    if len(candidates) > 1:
        empty['sources'] = [{**row, 'id': f'period_source_{index}'} for index, row in enumerate(candidates)]
    return empty


_BASIS_LABELS = {
    'age': r'연령|나이|생년월일|출생', 'residence': r'거주|주소|주민등록',
    'work_continuity': r'근로|재직|고용', 'issue_date': r'발급|발행', 'income': r'소득',
}


def _basis(lines: list[dict[str, Any]], kind: str) -> tuple[str | None, dict[str, Any] | None]:
    specific, common = [], []
    for line in lines:
        text, dates = line['text'], _dates(line['text'])
        if len(dates) != 1 or not re.search(r'기준|공고일', text):
            continue
        scopes = [name for name, pattern in _BASIS_LABELS.items() if re.search(pattern, text)]
        if scopes:
            if scopes == [kind]:
                specific.append((dates[0].isoformat(), line))
        elif re.search(r'공고일|공고\s*기준|^\s*기준일\s*[:：]', text):
            common.append((dates[0].isoformat(), line))
    candidates = specific or common
    if len({value for value, _ in candidates}) == 1:
        return candidates[0]
    return None, None


def _secondary_evidence(item: dict[str, Any], basis: str | None, line: dict[str, Any] | None,
                        primary: dict[str, Any]) -> None:
    if basis and line and line is not primary:
        item['basis_evidence'] = _evidence('basis', basis, line)


def _unparsed_condition(text: str) -> bool:
    """Any unconsumed qualifier is retained for an officer; it never disappears."""
    text = _DATE.sub('', text)
    text = _AGE.sub('', text)
    text = _PROVINCE.sub('', text)
    text = _CITY.sub('', text)
    text = re.sub(r'(?:기준\s*)?중위\s*소득\s*\d+(?:\.\d+)?\s*%\s*(?:이하|미만)?', '', text)
    text = re.sub(r'\d{1,2}\s*(?:개월|달|년)', '', text)
    vocabulary = ('생년월일', '신청기간', '기준일', '공고일', '전북특별자치도', '주민등록',
        '계속', '연속', '지속', '거주자', '지원', '신청', '모집', '대상', '자격', '연령', '나이',
        '요건', '조건', '기준', '사업', '청년', '출생자', '출생', '거주', '주소', '지역', '시도',
        '서류', '발급분', '발행분', '발급', '발행', '이후', '부터', '인정', '근로', '재직', '고용',
        '소득', '이상', '이하', '입니다', '합니다', '한다', '이며', '이고', '으로', '로서', '에서')
    for word in sorted(vocabulary, key=len, reverse=True):
        text = text.replace(word, '')
    text = re.sub(r'[\s\d.,:：;·ㆍ~∼～/()\[\]{}\-+%<>]', '', text)
    text = re.sub(r'^(?:은|는|의|에|를|을|와|과|인|자|만|및|또는|분|세|만|이|며|함)+$', '', text)
    return bool(text)


def _birth_range(low: int, high: int, basis: str) -> tuple[str, str] | None:
    """Compile an inclusive age interval into the existing birth-range contract."""
    day = date.fromisoformat(basis)
    try:
        # If the basis is leap day, the oldest/youngest anniversary's missing
        # calendar day is ambiguous. Keep it for human entry instead of guessing.
        start = day.replace(year=day.year - high - 1) + timedelta(days=1)
        end = day.replace(year=day.year - low)
    except ValueError:
        return None
    return start.isoformat(), end.isoformat()


def _required_docs(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from .api.posting_workspace import slot_catalog
    catalog = slot_catalog()
    aliases = {key: set((req.label, str(req.doc_type))) for key, req in catalog.items()}
    for key, names in _DOC_ALIASES.items():
        if key in aliases:
            aliases[key].update(names)
    # Equivalent work slots differ across programs; pick the first catalog slot
    # with the canonical document type rather than inventing an unsupported key.
    for key, req in catalog.items():
        if '4대보험' in str(req.doc_type):
            aliases[key].update(_DOC_ALIASES['work_proof_1'])
    result = []
    used = set()
    for line in lines:
        compact = re.sub(r'\s+', '', line['text'])
        found = []
        for key, names in aliases.items():
            if any(re.sub(r'\s+', '', name) in compact for name in names if name):
                found.append(key)
                if key in used:
                    continue
                # Multiple work categories can expose the same type. Avoid
                # manufacturing multiple required uploads from one printed name.
                signature = str(catalog[key].doc_type)
                if signature in used:
                    continue
                used.update((key, signature))
                item = _evidence(_id('document_' + key, line), key, line, .8)
                item.pop('value')
                item.update(type='document', slot_key=key, label=catalog[key].label,
                            required=not bool(re.search(r'(선택|해당자만|해당자에\s*한)', line['text'])))
                result.append(item)
        if re.search(r'제출\s*서류\s*[:：]', line['text']):
            raw = re.split(r'[:：]', line['text'], maxsplit=1)[-1]
            for part in re.split(r'[,，·ㆍ;]', raw):
                label = part.strip(' -•①②③④⑤⑥⑦⑧⑨⑩')
                label_compact = re.sub(r'\s+', '', label)
                if not label or any(re.sub(r'\s+', '', name) in label_compact for names in aliases.values() for name in names if name):
                    continue
                if label in used:
                    continue
                used.add(label)
                item = _evidence(_id('document_other_' + label, line), None, line, .35)
                item.pop('value')
                item.update(type='document', slot_key=None, label='기타 서류', original_label=label[:200], required=True,
                            review_reason='기존 제출 서류 슬롯에 연결할 수 없어 담당자 확인이 필요합니다.')
                result.append(item)
    return result


def _income_table(lines: list[dict[str, Any]]) -> dict[int, dict[str, int]]:
    """Extract only a fully labelled workplace/local/mixed premium table."""
    table = {}
    for index, line in enumerate(lines):
        if not all(word in line['text'] for word in ('가구', '직장', '지역')):
            continue
        for row in lines[index + 1:index + 12]:
            if row['page'] != line['page']:
                break
            match = re.fullmatch(r'\s*(\d{1,2})\s*인(?:\s*가구)?\s+([\d,]+)\s+([\d,]+)(?:\s+([\d,]+))?\s*', row['text'])
            if not match:
                break
            values = {'직장': int(match[2].replace(',', '')), '지역': int(match[3].replace(',', ''))}
            if match[4]:
                values['혼합'] = int(match[4].replace(',', ''))
            size = int(match[1])
            if size in table and table[size] != values:
                return {}
            table[size] = values
    return table


def _criteria(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    bases = {kind: _basis(lines, kind) for kind in SUPPORTED_RULES}
    for line in lines:
        text, dates = line['text'], _dates(line['text'])
        recognized = False
        initial_count = len(result)
        if ('출생' in text or '생년월일' in text) and len(dates) >= 2:
            basis, basis_line = bases['age']
            values = {'birth_start': dates[0].isoformat(), 'birth_end': dates[1].isoformat(), 'basis_date': basis}
            supported = len(dates) == 2 and dates[0] <= dates[1] and not re.search(r'미만|초과|제외|이전|이후', text)
            result.append(_criterion('age', line, values, supported=supported,
                reason='' if supported else '출생일 범위의 연산과 기준을 직접 확인해 주세요.'))
            recognized = True
        elif (age := _AGE.search(text)):
            basis, basis_line = bases['age']
            low, high = int(age[1]), int(age[2])
            interval = _birth_range(low, high, basis) if basis and 0 <= low <= high <= 120 else None
            supported = interval is not None and not re.search(r'미만|초과|제외|넘는|미만|[<>]', text)
            values = {'min_age': low, 'max_age': high, 'basis_date': basis,
                'birth_start': interval[0] if interval else '', 'birth_end': interval[1] if interval else ''}
            item = _criterion('age', line, values, supported=supported,
                reason='' if supported else '연령 연산 또는 기준일이 불명확하여 직접 확인해야 합니다.')
            _secondary_evidence(item, basis, basis_line, line)
            result.append(item)
            recognized = True
        if re.search(r'(거주|주소|주민등록)', text) and (province := _PROVINCE.search(text)):
            basis, basis_line = bases['residence']
            city = _CITY.search(text)
            name = {'전북': '전북특별자치도', '전라북도': '전북특별자치도'}.get(province[1], province[1])
            values = {'province': name, 'city': city[1] if city else '', 'basis_date': basis}
            supported = bool(basis) and city is None and not re.search(r'\d+\s*(개월|달|년)|계속|연속|지속|제외|이외|아닌', text)
            item = _criterion('residence', line, values, supported=supported,
                reason='' if supported else '시군·거주 기간·기준일 등 시도 현재주소 이외 조건을 직접 확인해야 합니다.')
            _secondary_evidence(item, basis, basis_line, line)
            result.append(item)
            recognized = True
        if re.search(r'(발급|발행)', text) and (dates or '공고일' in text) and re.search(r'(이후|부터|기준|이내)', text):
            basis, basis_line = bases['issue_date']
            cutoff = dates[0].isoformat() if len(dates) == 1 else basis if not dates else None
            scoped = re.search(r'초본|확인서|통장|사본|신청서|서약서|서류별|해당\s*서류|한하여|한정', text)
            supported = bool(cutoff) and bool(re.search(r'이후|부터', text)) and not scoped and not re.search(r'이내|이전|초과|미만|제외', text)
            item = _criterion('issue_date', line, {'mode': 'after_date', 'date': cutoff, 'basis_date': cutoff},
                supported=supported, reason='' if supported else '서류별 발급일 범위 또는 연산은 일괄 자동 규칙에 연결하지 않고 직접 확인합니다.')
            if not dates:
                _secondary_evidence(item, basis, basis_line, line)
            result.append(item)
            recognized = True
        if percent := re.search(r'(?:기준\s*)?중위\s*소득\s*(\d{1,3}(?:\.\d+)?)\s*%\s*(이하|미만)?', text):
            from .rules.scoring import MEDIAN_INCOME_140
            table = _income_table(lines)
            amount = float(percent[1])
            supported = amount == 140 and percent[2] == '이하' and table == MEDIAN_INCOME_140
            item = _criterion('income', line, {'percent': amount, 'operator': percent[2] or '', 'household_table': table},
                supported=supported, reason='' if supported else '가구원 기준표가 없거나 기존 엔진의 확정 기준표와 달라 담당자 확인이 필요합니다.')
            if table:
                evidence = []
                for row in lines:
                    if all(word in row['text'] for word in ('가구', '직장', '지역')) or re.fullmatch(r'\s*\d{1,2}\s*인(?:\s*가구)?\s+[\d,]+\s+[\d,]+(?:\s+[\d,]+)?\s*', row['text']):
                        evidence.append(_evidence(f'income_table_{len(evidence)}', row['text'], row))
                item['table_evidence'] = evidence
            result.append(item)
            recognized = True
        if re.search(r'(계속|연속|지속)', text) and re.search(r'(근로|재직|고용)', text):
            basis, basis_line = bases['work_continuity']
            duration = re.search(r'(\d{1,2})\s*(개월|달|년)', text)
            months = int(duration[1]) * (12 if duration[2] == '년' else 1) if duration else None
            supported = bool(months and 0 < months <= 120 and basis) and not re.search(r'이하|미만|이내|최대|초과|제외|누적|합산', text)
            item = _criterion('work_continuity', line, {'months': months, 'basis_date': basis},
                supported=supported, reason='' if supported else '근로 연산·기간·기준일이 기존 계속성 규칙과 같다고 확정할 수 없습니다.')
            _secondary_evidence(item, basis, basis_line, line)
            result.append(item)
            recognized = True
        if recognized and re.search(r'또는|혹은|이거나', text):
            for candidate in result[initial_count:]:
                candidate.update(type='checklist', engine_rule=None,
                    review_reason='선택 가능한 복합 조건은 개별 자동 규칙의 결합으로 해석하지 않고 직접 확인합니다.')
        automatic = any(row['type'] != 'checklist' for row in result[initial_count:])
        if recognized and automatic and _unparsed_condition(text):
            result.append(_criterion('checklist', line, {}, supported=False,
                reason='자동 후보로 설명되지 않은 조건이 남아 있어 원문 전체를 담당자가 확인해야 합니다.'))
        elif not recognized and re.search(r'(요건|자격|대상|기준|조건|제외|필수|가능하여야|하여야|해야)', text):
            if not re.search(r'(신청|접수|모집)\s*기간|가구.*직장.*지역|공고일\s*[:：]|기준일\s*[:：]', text):
                result.append(_criterion('checklist', line, {}, supported=False,
                    reason='기존 엔진에서 지원하는 자동 규칙에 연결되지 않은 항목입니다.'))
    return list({item['id']: item for item in result}.values())


def analyze_notice(pdf: bytes, supplemental: str = '') -> dict[str, Any]:
    if not isinstance(supplemental, str) or len(supplemental) > MAX_SUPPLEMENTAL:
        raise ValueError('부가 설명문은 4,000자 이하로 입력해 주세요.')
    pages = notice_pages(pdf)
    lines = _lines(pages, supplemental)
    notice_lines = [row for row in lines if row['source'] == 'notice']
    title_candidates = [row for row in notice_lines[:30] if re.search(r'(사업|지원|모집)', row['text'])
                        and not re.search(r'기간|서류|대상|요건|자격|조건|방법|문의|제\s*\d+\s*호', row['text'])]
    title_ambiguous = len({row['text'] for row in title_candidates}) > 1
    title_line = title_candidates[0] if title_candidates and not title_ambiguous else None
    if title_line is None and not title_ambiguous:
        title_line = next((row for row in notice_lines[:10] if len(row['text']) > 3 and '공고 제' not in row['text']), None)
    title_value = title_line['text'].strip('「」『』“”')[:100] if title_line else ''
    title = _evidence('title', title_value, title_line)
    period = _period(lines)
    documents = _required_docs(lines)
    criteria = _criteria(lines)
    audience = next((row for row in lines if re.search(r'(지원|신청|모집)\s*대상\s*[:：]', row['text'])), None)
    method = next((row for row in lines if re.search(r'(신청|접수)\s*방법\s*[:：]', row['text'])), None)
    contact = next((row for row in lines if re.search(r'(문의|연락처)\s*[:：]', row['text'])), None)
    guidance_parts = [f'{title_value} 신청 안내' if title_value else '사업 제목을 입력해 주세요.']
    guidance_parts.append(audience['text'] if audience else '지원 대상: 공고문의 신청 자격을 확인해 주세요.')
    dates = period['value']
    guidance_parts.append(f'신청 기간: {dates["apply_start"]} ~ {dates["apply_end"]}' if all(dates.values()) else '신청 기간: 공고문에서 확인하여 입력해 주세요.')
    guidance_parts.append(method['text'] if method else '신청 방법: 공고문의 접수 방법을 확인해 주세요.')
    guidance_parts.append('제출 서류: ' + ', '.join(row.get('original_label', row['label']) for row in documents) if documents else '제출 서류: 공고문에서 확인하여 입력해 주세요.')
    guidance_parts.append(contact['text'] if contact else '문의: 공고문의 문의처를 확인해 주세요.')
    guidance = _evidence('guidance', '\n'.join(guidance_parts), audience or title_line, .6)
    guidance['sources'] = [_evidence(f'guidance_source_{index}', row['text'], row) for index, row in enumerate((audience, method, contact)) if row]
    has_text = bool(notice_lines)
    warnings = [] if has_text else ['자동 분석 불가 → 직접 입력: 공고문의 글자층이 없습니다.']
    if title_ambiguous:
        warnings.append('서로 다른 사업 제목 후보가 있어 직접 확인해야 합니다.')
    if len(_period_candidates(lines)) > 1:
        warnings.append('서로 다른 신청 기간이 있어 자동 선택하지 않았습니다. 적용 기간을 직접 확인해 주세요.')
    return {'version': 1, 'status': 'draft' if has_text else 'manual_required',
            'title': title, 'period': period, 'guidance': guidance,
            'required_docs': documents, 'criteria': criteria, 'source_pages': pages,
            'warnings': warnings}


def analyze_form(pdf: bytes, *, form_no: str = 'form_1', title: str = '서식', template: str = '') -> dict[str, Any]:
    """Reuse the established five-stage layout detector without changing it."""
    return draft_layout(pdf, form_no=form_no, title=title, template=template)
