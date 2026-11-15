"""Isolated synthetic-only E2E server; never opens the repository runtime DB or storage.

Run: uvicorn e2e_backend:app --app-dir <this dir> --port 8031 --env-file .env
Values from .env are overridden below with synthetic ones; API keys are removed.
"""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.update({'ENGINE_V2_OCR': 'off', 'OFFICER_PASSWORD': 'synthetic-e2e-password',
                   'OFFICER_SESSION_SECRET': 'synthetic-e2e-session-secret-for-local-run',
                   'LLM_PROVIDER': 'none', 'PROGRAM_LLM_PROVIDER': 'none', 'PROGRAM_LLM_ENABLED': 'false',
                   'JBAI_ALLOW_REAL_DOCS': 'false'})
for key in ('JBAI_API_KEY', 'UPSTAGE_API_KEY'):
    os.environ.pop(key, None)

from sqlmodel import create_engine  # noqa: E402
from demo.backend import models  # noqa: E402
from demo.backend.main import app  # noqa: E402
from demo.backend.api import applications, common, documents, files, forms, postings  # noqa: E402

ROOT = Path('/tmp/form-draft-detection-e2e')
STORAGE = ROOT / 'storage'
STORAGE.mkdir(parents=True, exist_ok=True)
models.DB_PATH = ROOT / 'demo.db'
models.engine = create_engine(f'sqlite:///{models.DB_PATH}', connect_args={'check_same_thread': False})
models.SQLModel.metadata.create_all(models.engine)
for module in (applications, common, documents, files, forms, postings):
    module.STORAGE = STORAGE
applications.SIGNATURES = STORAGE / 'signatures'
documents.DOCUMENTS = STORAGE / 'documents'
