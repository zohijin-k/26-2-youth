"""Isolated synthetic-only server with a fake notice provider (no network, no .env).

Run: E2E_ROOT=<dir> .venv/bin/python -m uvicorn e2e_backend:app --app-dir <this dir> --port 8033
DB, storage and the synthetic notice live under E2E_ROOT; the repository runtime DB is never opened.
"""
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
os.environ.update({'ENGINE_V2_OCR': 'off', 'OFFICER_PASSWORD': 'synthetic-e2e-password',
                   'OFFICER_SESSION_SECRET': 'synthetic-e2e-session-secret-for-local-run',
                   'LLM_PROVIDER': 'none', 'PROGRAM_LLM_PROVIDER': 'none', 'PROGRAM_LLM_ENABLED': 'false',
                   'JBAI_ALLOW_REAL_DOCS': 'false'})
for key in [name for name in os.environ if name.startswith('JBAI_') and name != 'JBAI_ALLOW_REAL_DOCS']:
    os.environ.pop(key, None)

from sqlmodel import create_engine  # noqa: E402
from demo.backend import models  # noqa: E402
from demo.backend.main import app  # noqa: E402,F401
from demo.backend.api import applications, common, documents, files, forms, postings  # noqa: E402

ROOT = Path(os.environ['E2E_ROOT'])
STORAGE = ROOT / 'storage'
STORAGE.mkdir(parents=True, exist_ok=True)
models.DB_PATH = ROOT / 'demo.db'
models.engine = create_engine(f'sqlite:///{models.DB_PATH}', connect_args={'check_same_thread': False})
models.SQLModel.metadata.create_all(models.engine)
for module in (applications, common, documents, files, forms, postings):
    module.STORAGE = STORAGE
applications.SIGNATURES = STORAGE / 'signatures'
documents.DOCUMENTS = STORAGE / 'documents'


from datetime import datetime  # noqa: E402
from sqlmodel import select  # noqa: E402
from demo.backend.rules.programs import JOB_PACKAGE  # noqa: E402


def _seed(number, ai, docs, day):
    with models.get_session() as session:
        if session.exec(select(models.Application).where(models.Application.application_no == f'E2E-{number:03}')).first():
            return
        row = models.Application(application_no=f'E2E-{number:03}', program_code=JOB_PACKAGE, status=models.STATUS_SUBMITTED,
            criteria_version=1, form1_json={'name': f'가상신청{number}', 'address': '전북특별자치도 전주시 가상동 0'},
            submitted_at=datetime(2026, 11, day, 9, number))
        session.add(row); session.commit(); session.refresh(row)
        session.add(models.Review(application_id=row.id, final_status=ai))
        for slot, status, message in docs:
            session.add(models.Document(application_id=row.id, slot_key=slot, file_path=f'documents/E2E-{slot}.pdf', file_format='pdf',
                stage1_status=status, findings_json=[{'code': 'E2E', 'message': message, 'severity': status}] if message else [],
                ocr_json={'fields': {}}))
        session.commit()


_seed(1, 'PASS', [('resident_abstract', 'PASS', None)], 1)
_seed(2, 'FAIL', [('resident_abstract', 'FAIL', '주민등록초본 발급일이 기준일보다 빠릅니다.'),
                  (models.UNASSIGNED_SLOT, 'NEEDS_REVIEW', '배정되지 않은 페이지가 있습니다.')], 2)
_seed(3, 'NEEDS_REVIEW', [('resident_abstract', 'NEEDS_REVIEW', '주소가 흐려 확인이 필요합니다.')], 3)


@app.get('/api/__e2e/review/{application_no}')
def stored_review(application_no: str) -> dict:
    """Harness-only: what the reject page stored."""
    with models.get_session() as session:
        row = session.exec(select(models.Application).where(models.Application.application_no == application_no)).one()
        review = session.exec(select(models.Review).where(models.Review.application_id == row.id)).one()
        return {'id': row.id, 'status': row.status, 'decision': review.officer_decision,
                'memo': review.officer_memo, 'notice': review.reject_notice}
