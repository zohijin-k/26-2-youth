"""Isolated synthetic-only server with a fake notice provider (no network, no .env).

Run: .venv/bin/python -m uvicorn e2e_backend:app --app-dir <this dir> --port 8032
DB and storage live under /tmp/jbai-schema-check-e2e; the repository runtime DB is never opened.
"""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.update({'ENGINE_V2_OCR': 'off', 'OFFICER_PASSWORD': 'synthetic-e2e-password',
                   'OFFICER_SESSION_SECRET': 'synthetic-e2e-session-secret-for-local-run',
                   'LLM_PROVIDER': 'none', 'PROGRAM_LLM_PROVIDER': 'none', 'PROGRAM_LLM_ENABLED': 'false',
                   'JBAI_ALLOW_REAL_DOCS': 'false'})
for key in [name for name in os.environ if name.startswith('JBAI_') and name != 'JBAI_ALLOW_REAL_DOCS']:
    os.environ.pop(key, None)

from sqlmodel import create_engine  # noqa: E402
from demo.backend import models, notice_llm  # noqa: E402
from demo.backend.main import app  # noqa: E402,F401
from demo.backend.api import applications, common, documents, files, forms, postings  # noqa: E402

ROOT = Path('/tmp/jbai-schema-check-e2e')
STORAGE = ROOT / 'storage'
STORAGE.mkdir(parents=True, exist_ok=True)
models.DB_PATH = ROOT / 'demo.db'
models.engine = create_engine(f'sqlite:///{models.DB_PATH}', connect_args={'check_same_thread': False})
models.SQLModel.metadata.create_all(models.engine)
for module in (applications, common, documents, files, forms, postings):
    module.STORAGE = STORAGE
applications.SIGNATURES = STORAGE / 'signatures'
documents.DOCUMENTS = STORAGE / 'documents'

AGE = {'min_age': 18, 'max_age': 39, 'basis_date': '2026-11-15', 'birth_start': '1986-11-16', 'birth_end': '2008-11-15'}


class FakeNoticeProvider:
    """Stands in for JBAI: one verifiable guidance and one verifiable age proposal, plus a bad one."""
    name = 'jbai'

    def generate(self, purpose, payload):
        assert purpose == 'notice_analysis' and set(payload) == {'notice_pages', 'supplemental'}
        return json.dumps({'guidance': {'text': '신청 방법: 온라인 신청', 'page': 1, 'quote': '신청 방법: 온라인 신청'},
            'criteria': [
                {'type': 'age', 'values_json': json.dumps(AGE), 'page': 1, 'quote': '지원 대상: 만 18세 이상 39세 이하 청년'},
                {'type': 'residence', 'values_json': json.dumps({'province': '서울'}), 'page': 1,
                 'quote': '거주 요건: 전북특별자치도 거주자'},
            ]}, ensure_ascii=False)


notice_llm.configured_notice_provider = lambda **kwargs: FakeNoticeProvider()
