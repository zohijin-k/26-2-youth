"""Isolated synthetic-only visual test server; never opens repository runtime DB."""
import os
from pathlib import Path
from sqlmodel import create_engine

os.environ['ENGINE_V2_OCR'] = 'off'
os.environ['OFFICER_PASSWORD'] = 'synthetic-visual-password'
os.environ['OFFICER_SESSION_SECRET'] = 'synthetic-visual-session-secret'
os.environ['LLM_PROVIDER'] = 'none'
os.environ['JBAI_ALLOW_REAL_DOCS'] = 'false'
os.environ['PROGRAM_LLM_PROVIDER'] = 'none'
os.environ['PROGRAM_LLM_ENABLED'] = 'false'
for key in ('JBAI_API_KEY', 'UPSTAGE_API_KEY'):
    os.environ.pop(key, None)
from demo.backend import models
from demo.backend.main import app
from demo.backend.api import applications, common, documents, files, forms, postings

ROOT = Path(os.environ.get('RENEWAL_VISUAL_ROOT', '/tmp/renewal-master2-visual'))
STORAGE = ROOT / 'storage'
STORAGE.mkdir(parents=True, exist_ok=True)
models.DB_PATH = ROOT / 'demo.db'
models.engine = create_engine(f'sqlite:///{models.DB_PATH}', connect_args={'check_same_thread': False})
for module in (applications, common, documents, files, forms, postings):
    module.STORAGE = STORAGE
applications.SIGNATURES = STORAGE / 'signatures'
documents.DOCUMENTS = STORAGE / 'documents'


@app.get('/__visual__/counts')
def visual_counts():
    """Value-free counters exist only in this isolated visual-server wrapper."""
    from sqlmodel import select
    with models.get_session() as session:
        return {'applications': len(session.exec(select(models.Application)).all()),
                'postings': len(session.exec(select(models.ProgramPosting)).all())}

# Synthetic-only support endpoints exist in this isolated runner, never main.
(ROOT / '.renewal-master2-synthetic').write_text('renewal-master-2')
import visual_job
app.get('/__visual__/identity')(visual_job.visual_identity)

@app.post('/__visual__/job/{application_id}/seed')
def seed_visual_job(application_id: int):
    return visual_job.seed_job(application_id)
