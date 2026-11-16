"""Isolated synthetic-only server with a fake notice provider (no network, no .env).

Run: E2E_ROOT=<dir> .venv/bin/python -m uvicorn e2e_backend:app --app-dir <this dir> --port 8033
DB, storage and the synthetic notice live under E2E_ROOT; the repository runtime DB is never opened.
"""
import json
import os
from pathlib import Path
import shutil
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
os.environ.update({'ENGINE_V2_OCR': 'off', 'OFFICER_PASSWORD': 'synthetic-e2e-password',
                   'OFFICER_SESSION_SECRET': 'synthetic-e2e-session-secret-for-local-run',
                   'LLM_PROVIDER': 'none', 'PROGRAM_LLM_PROVIDER': 'none', 'PROGRAM_LLM_ENABLED': 'false',
                   'JBAI_ALLOW_REAL_DOCS': 'false'})
for key in [name for name in os.environ if name.startswith('JBAI_') and name != 'JBAI_ALLOW_REAL_DOCS']:
    os.environ.pop(key, None)

import pymupdf  # noqa: E402
from sqlmodel import create_engine  # noqa: E402
from demo.backend import models, notice_llm  # noqa: E402
from demo.backend.main import app  # noqa: E402,F401
from demo.backend.api import applications, common, documents, files, forms, postings  # noqa: E402

ROOT = Path(os.environ['E2E_ROOT'])
STORAGE = ROOT / 'storage'
FILES = ROOT / 'files'
STORAGE.mkdir(parents=True, exist_ok=True)
FILES.mkdir(parents=True, exist_ok=True)
models.DB_PATH = ROOT / 'demo.db'
models.engine = create_engine(f'sqlite:///{models.DB_PATH}', connect_args={'check_same_thread': False})
models.SQLModel.metadata.create_all(models.engine)
for module in (applications, common, documents, files, forms, postings):
    module.STORAGE = STORAGE
applications.SIGNATURES = STORAGE / 'signatures'
documents.DOCUMENTS = STORAGE / 'documents'

NOTICE = [
    '2026 합성 청년 구직지원사업 모집 공고',
    '공고일: 2026.11.16',
    '1. 모집개요',
    '가. 사업목적: 지역 청년의 구직 활동을 돕습니다.',
    '나. 지원대상: 전북특별자치도 거주 만 18세 이상 39세 이하 청년',
    '다. 지원내용: 월 30만원, 최대 6개월 지원',
    '라. 모집인원: 100명',
    '마. 신청기간: 2026.11.16 ~ 2026.12.31',
    '2. 신청자격',
    '가. 공고일 현재 미취업 상태인 사람',
    '3. 제출서류',
    '제출 서류: 주민등록초본, 활동계획서',
    '신청 방법: 온라인 신청',
    '문의: 합성청년센터 063-000-0000',
]
with pymupdf.open() as document:
    page = document.new_page(width=1000, height=1000)
    for index, line in enumerate(NOTICE):
        page.insert_text((30, 40 + 24 * index), line, fontname='korea', fontsize=11)
    (FILES / 'notice.pdf').write_bytes(document.tobytes())
shutil.copyfile(REPO / 'demo/fixtures/templates/job_consent.pdf', FILES / 'form.pdf')

GUIDANCE = '\n'.join([
    '2026 합성 청년 구직지원사업은 지역 청년의 구직 활동을 돕는 사업입니다.',
    '지원 대상: 전북특별자치도에 사는 만 18세 이상 39세 이하 청년',
    '지원 내용: 월 30만원씩 최대 6개월 동안 지원합니다.',
    '모집 인원: 100명',
    '신청 기간: 2026년 11월 16일부터 12월 31일까지',
    '신청 방법: 온라인으로 신청해 주세요.',
])


class FakeNoticeProvider:
    """Stands in for JBAI: writes guidance from the overview (numbers all in the notice)."""
    name = 'jbai'

    def generate(self, purpose, payload):
        assert purpose == 'notice_analysis' and set(payload) == {'notice_pages', 'supplemental'}
        return json.dumps({'guidance': {'text': GUIDANCE, 'page': 1, 'quote': '1. 모집개요'}, 'criteria': []},
                          ensure_ascii=False)


notice_llm.configured_notice_provider = lambda **kwargs: FakeNoticeProvider()


@app.post('/api/__e2e/force-publish/{posting_id}')
def force_publish(posting_id: int) -> dict:
    """Harness-only shortcut: mark a draft published to check the published-state buttons."""
    with models.get_session() as session:
        row = session.get(models.ProgramPosting, posting_id)
        row.status = models.POSTING_PUBLISHED
        session.add(row)
        session.commit()
    return {'ok': True}
