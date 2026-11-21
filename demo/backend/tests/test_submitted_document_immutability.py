"""Synthetic-only applicant evidence immutability and original-byte regression."""
from datetime import datetime
from hashlib import sha256
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlmodel import select

from demo.backend import models
from demo.backend.api import common, documents, forms
from demo.backend.ocr.base import OcrResult
from demo.backend.rules.doc_types import DocType
from demo.backend.tests.test_portal_uploads import client
from demo.backend.tests.run_p5_scenarios import create_job_application, S10_SELECTION, S10_UPLOADS
from demo.backend.tests.test_generic_programs import pdf


def snapshot():
    with models.get_session() as session:
        database = {table.name: sorted([dict(row) for row in session.execute(table.select()).mappings()], key=repr)
                    for table in models.SQLModel.metadata.sorted_tables}
    storage = {str(p.relative_to(common.STORAGE)): sha256(p.read_bytes()).hexdigest()
               for p in common.STORAGE.rglob('*') if p.is_file()}
    return database, storage


def seed(client, program='job_package', status='submitted'):
    response = client.post('/api/applications', json={'program_code': program})
    assert response.status_code == 200, response.text
    aid = response.json()['id']
    path = common.STORAGE / 'documents' / f'synthetic-{aid}.pdf'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pdf())
    archive = common.STORAGE / f'synthetic-archive-{aid}.pdf'
    archive.write_bytes(pdf(True))
    with models.get_session() as session:
        app = session.get(models.Application, aid)
        app.status = status
        app.submitted_at = datetime(2026,11,22,10,0) if status != 'draft' else None
        app.written_forms_archive_path = str(archive.relative_to(common.STORAGE.parent))
        app.written_forms_archive_count = 1
        row = models.Document(application_id=aid,slot_key='resident_abstract',
                              file_path=str(path.relative_to(common.STORAGE.parent)),file_format='pdf',
                              stage1_status='PASS',ocr_json={'synthetic':'unchanged'},
                              findings_json=[{'code':'SYNTHETIC','severity':'INFO'}])
        session.add(app); session.add(row)
        session.add(models.Review(application_id=aid,final_status='PASS',officer_memo='synthetic memo',
                                  review_payload_json={'synthetic':'original evidence'}))
        session.commit(); session.refresh(row)
        return aid,row.id,path


@pytest.mark.parametrize('program',['job_package','double_savings'])
@pytest.mark.parametrize('status',['submitted','reviewing','decided','unknown_future_state'])
@pytest.mark.parametrize('action',['upload','delete'])
def test_non_draft_rejects_before_processing_and_preserves_every_table_and_file(client,monkeypatch,program,status,action):
    aid,did,path=seed(client,program,status)
    before=snapshot()
    def forbidden(*args,**kwargs):
        raise AssertionError('Rejected request processed evidence')
    for name in ['read_document','assess_upload','_replace_existing','_save_row','_refresh_nhis_identity','_upload_merged','_upload_bankbook']:
        monkeypatch.setattr(documents,name,forbidden)
    if action=='upload':
        response=client.post(f'/api/applications/{aid}/documents',data={'slot_key':'resident_abstract'},
                             files={'file':('replacement.pdf',pdf(True),'application/pdf')})
    else: response=client.delete(f'/api/applications/{aid}/documents/{did}')
    assert response.status_code==409,response.text
    assert response.json()['detail']=='제출한 신청서는 수정할 수 없습니다.'
    assert snapshot()==before
    assert client.get(f'/api/files/{did}').content==path.read_bytes()
    assert client.get(f'/api/officer/applications/{aid}').status_code==200


@pytest.mark.parametrize('action',['upload','delete'])
def test_real_job_submission_rejects_mutation_and_preserves_review(client,monkeypatch,action):
    monkeypatch.setattr(forms,'STORAGE',common.STORAGE)
    aid=create_job_application(client,selections=S10_SELECTION,uploads=S10_UPLOADS)
    with models.get_session() as session:
        row=session.exec(select(models.Document).where(models.Document.application_id==aid,models.Document.slot_key=='resident_abstract')).one()
        did=row.id; filename=Path(row.file_path).name
    assert client.get(f'/api/applications/{aid}/final-check').json()['can_submit']
    assert client.post(f'/api/applications/{aid}/submit').status_code==200
    before=snapshot()
    if action=='upload':
        response=client.post(f'/api/applications/{aid}/documents',data={'slot_key':'resident_abstract'},
                             files={'file':(filename,pdf(True),'application/pdf')})
    else: response=client.delete(f'/api/applications/{aid}/documents/{did}')
    assert response.status_code==409,response.text
    assert snapshot()==before


def test_internal_replace_cannot_bypass_fresh_status(client):
    aid,did,_=seed(client)
    before=snapshot()
    with pytest.raises(HTTPException) as error:
        documents._replace_existing(aid,'resident_abstract')
    assert error.value.status_code==409
    assert snapshot()==before


def test_internal_save_cannot_bypass_fresh_status(client):
    aid,did,path=seed(client,status='draft')
    with models.get_session() as session: stale=session.get(models.Application,aid)
    with models.get_session() as session:
        current=session.get(models.Application,aid); current.status='submitted';session.add(current);session.commit()
    before=snapshot()
    with pytest.raises(HTTPException) as error:
        documents._save_row(stale,None,'resident_abstract',path,OcrResult(detected_doc_type=DocType.RESIDENT_ABSTRACT),None,[],'PASS',replace_existing=True)
    assert error.value.status_code==409
    assert snapshot()==before


def test_document_id_of_another_application_remains_private(client):
    aid,_,_=seed(client,status='draft')
    other,did,_=seed(client,status='draft')
    before=snapshot()
    assert client.delete(f'/api/applications/{aid}/documents/{did}').status_code==404
    assert snapshot()==before


def test_draft_same_name_replacement_preserves_previous_bytes_and_delete(client):
    aid,did,original=seed(client,status='draft')
    prior=original.read_bytes()
    source=pdf(True)
    upload=client.post(f'/api/applications/{aid}/documents',data={'slot_key':'resident_abstract'},
                       files={'file':(original.name,source,'application/pdf')})
    assert upload.status_code==200,upload.text
    new_id=upload.json()['document_id']
    with models.get_session() as session:
        rows=session.exec(select(models.Document).where(models.Document.application_id==aid)).all()
        assert len(rows)==1
        target=common.STORAGE.parent/rows[0].file_path
    assert target!=original and original.read_bytes()==prior
    assert target.read_bytes()==source
    assert client.delete(f'/api/applications/{aid}/documents/{new_id}').status_code==200
    assert not target.exists() and original.read_bytes()==prior


def test_failed_new_upload_rolls_back_replacement_and_removes_staged_file(client,monkeypatch):
    from contextlib import contextmanager
    aid,did,original=seed(client,status='draft')
    before=snapshot()
    real=documents.session_transaction
    @contextmanager
    def fail_commit():
        with real():
            yield
            raise RuntimeError('synthetic transaction failure')
    monkeypatch.setattr(documents,'session_transaction',fail_commit)
    with pytest.raises(RuntimeError,match='synthetic transaction failure'):
        client.post(f'/api/applications/{aid}/documents',data={'slot_key':'resident_abstract'},
                    files={'file':(original.name,pdf(True),'application/pdf')})
    assert snapshot()==before


def test_failed_delete_transaction_keeps_original_and_document(client,monkeypatch):
    from contextlib import contextmanager
    aid,did,original=seed(client,status='draft')
    before=snapshot()
    real=documents.session_transaction
    @contextmanager
    def fail_commit():
        with real():
            yield
            raise RuntimeError('synthetic transaction failure')
    monkeypatch.setattr(documents,'session_transaction',fail_commit)
    with pytest.raises(RuntimeError,match='synthetic transaction failure'):
        client.delete(f'/api/applications/{aid}/documents/{did}')
    assert snapshot()==before


@pytest.mark.parametrize('action',['upload','delete'])
def test_submit_wins_race_and_late_mutation_is_rejected(client,monkeypatch,action):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from demo.backend.api import review
    monkeypatch.setattr(forms,'STORAGE',common.STORAGE)
    aid=create_job_application(client,selections=S10_SELECTION,uploads=S10_UPLOADS)
    with models.get_session() as session:
        doc=session.exec(select(models.Document).where(models.Document.application_id==aid,models.Document.slot_key=='resident_abstract')).one()
        did=doc.id; filename=Path(doc.file_path).name
    entered,release=threading.Event(),threading.Event()
    real=review._run_review
    def paused(app):
        entered.set()
        assert release.wait(10)
        return real(app)
    monkeypatch.setattr(review,'_run_review',paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        submit=pool.submit(client.post,f'/api/applications/{aid}/submit')
        assert entered.wait(10)
        if action=='upload':
            mutation=pool.submit(client.post,f'/api/applications/{aid}/documents',data={'slot_key':'resident_abstract'},files={'file':(filename,pdf(True),'application/pdf')})
        else: mutation=pool.submit(client.delete,f'/api/applications/{aid}/documents/{did}')
        assert not mutation.done()
        release.set()
        assert submit.result(timeout=15).status_code==200
        assert mutation.result(timeout=15).status_code==409
    before=snapshot()
    assert client.delete(f'/api/applications/{aid}/documents/{did}').status_code==409
    assert snapshot()==before


def test_upload_wins_race_then_submission_uses_uploaded_original(client,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    monkeypatch.setattr(forms,'STORAGE',common.STORAGE)
    aid=create_job_application(client,selections=S10_SELECTION,uploads=S10_UPLOADS)
    with models.get_session() as session:
        doc=session.exec(select(models.Document).where(models.Document.application_id==aid,models.Document.slot_key=='resident_abstract')).one()
        filename=Path(doc.file_path).name
        source=(common.STORAGE.parent/doc.file_path).read_bytes()
    entered,release=threading.Event(),threading.Event()
    real=documents.assess_upload
    def paused(*args,**kwargs):
        entered.set()
        assert release.wait(10)
        return real(*args,**kwargs)
    monkeypatch.setattr(documents,'assess_upload',paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        upload=pool.submit(client.post,f'/api/applications/{aid}/documents',data={'slot_key':'resident_abstract'},files={'file':(filename,source,'application/pdf')})
        assert entered.wait(10)
        submit=pool.submit(client.post,f'/api/applications/{aid}/submit')
        assert not submit.done()
        release.set()
        uploaded=upload.result(timeout=15)
        assert uploaded.status_code==200,uploaded.text
        submitted=submit.result(timeout=15)
        assert submitted.status_code==200,submitted.text
    before=snapshot()
    assert client.get(uploaded.json()['file_url']).content==source
    assert client.delete(f'/api/applications/{aid}/documents/{uploaded.json()["document_id"]}').status_code==409
    assert snapshot()==before


def test_separate_process_lock_wait_cancellation_releases_descriptor(client):
    import asyncio
    import os
    import subprocess
    import sys
    from demo.backend.application_writes import async_application_write
    # Separate interpreter, separate descriptor, same synthetic DB namespace.
    code = '''
import sys
from sqlmodel import create_engine
from demo.backend import models
from demo.backend.application_writes import application_write
models.engine=create_engine(sys.argv[1])
with application_write(1):
    print('locked',flush=True)
    sys.stdin.readline()
'''
    child=subprocess.Popen([sys.executable,'-B','-c',code,str(models.engine.url)],
                           stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    try:
        assert child.stdout.readline().strip()=='locked'
        async def scenario():
            entered=asyncio.Event()
            async def waiter():
                async with async_application_write(1): entered.set()
            pending=asyncio.create_task(waiter())
            await asyncio.sleep(.05)
            assert not entered.is_set()
            pending.cancel()
            with pytest.raises(asyncio.CancelledError): await pending
            child.stdin.write('\n');child.stdin.flush()
            assert child.wait(timeout=10)==0
            # The cancelled waiter must not retain an orphan lock after the
            # child releases. A fresh acquisition must succeed immediately.
            async with asyncio.timeout(2):
                async with async_application_write(1): pass
        asyncio.run(scenario())
    finally:
        if child.poll() is None: child.kill();child.wait()
        child.stdin.close();child.stdout.close()


def test_delete_staging_failure_rolls_back_database_and_preserves_original(client,monkeypatch):
    aid,did,original=seed(client,status='draft')
    before=snapshot()
    real=Path.rename
    def fail(path,target):
        if path==original: raise OSError('synthetic rename failure')
        return real(path,target)
    monkeypatch.setattr(Path,'rename',fail)
    with pytest.raises(OSError,match='synthetic rename failure'):
        client.delete(f'/api/applications/{aid}/documents/{did}')
    assert snapshot()==before


def test_postcommit_cleanup_failure_does_not_report_failed_mutation(client,monkeypatch):
    aid,did,original=seed(client,status='draft')
    original_bytes=original.read_bytes()
    real=Path.unlink
    def fail(path,*args,**kwargs):
        if path.name.endswith('.pending-delete'): raise OSError('synthetic cleanup failure')
        return real(path,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',fail)
    response=client.delete(f'/api/applications/{aid}/documents/{did}')
    assert response.status_code==200,response.text
    with models.get_session() as session: assert session.get(models.Document,did) is None
    assert not original.exists()
    tombstones=list(original.parent.glob('*.pending-delete'))
    assert len(tombstones)==1 and tombstones[0].read_bytes()==original_bytes
    # Deterministic cleanup of the injected test-only failure.
    real(tombstones[0])


def test_two_same_slot_uploads_serialize_and_never_overwrite_prior_bytes(client,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    import time
    aid,did,_=seed(client,status='draft')
    entered,release=threading.Event(),threading.Event()
    real=documents.assess_upload
    paths=[]
    def paused(path,*args,**kwargs):
        paths.append(Path(path))
        if len(paths)==1:
            entered.set()
            assert release.wait(10)
        return real(path,*args,**kwargs)
    monkeypatch.setattr(documents,'assess_upload',paused)
    source1,source2=pdf(),pdf(True)
    def upload(source):
        return client.post(f'/api/applications/{aid}/documents',data={'slot_key':'resident_abstract'},
                           files={'file':('same.pdf',source,'application/pdf')})
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(upload,source1)
        assert entered.wait(10)
        second=pool.submit(upload,source2)
        time.sleep(.05)
        assert len(paths)==1 and not second.done()
        release.set()
        assert first.result(timeout=15).status_code==200
        assert second.result(timeout=15).status_code==200
    assert len(paths)==2 and paths[0]!=paths[1]
    assert paths[0].read_bytes()==source1 and paths[1].read_bytes()==source2
    with models.get_session() as session:
        rows=session.exec(select(models.Document).where(models.Document.application_id==aid,models.Document.slot_key=='resident_abstract')).all()
        assert len(rows)==1 and common.STORAGE.parent/rows[0].file_path==paths[1]


def test_delete_wins_race_and_submission_rechecks_missing_evidence(client,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager
    import threading
    monkeypatch.setattr(forms,'STORAGE',common.STORAGE)
    aid=create_job_application(client,selections=S10_SELECTION,uploads=S10_UPLOADS)
    with models.get_session() as session:
        doc=session.exec(select(models.Document).where(models.Document.application_id==aid,models.Document.slot_key=='resident_abstract')).one()
        did=doc.id;path=common.STORAGE.parent/doc.file_path
    entered,release=threading.Event(),threading.Event()
    real=documents.session_transaction
    @contextmanager
    def paused():
        with real():
            entered.set()
            assert release.wait(10)
            yield
    monkeypatch.setattr(documents,'session_transaction',paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        deletion=pool.submit(client.delete,f'/api/applications/{aid}/documents/{did}')
        assert entered.wait(10)
        submit=pool.submit(client.post,f'/api/applications/{aid}/submit')
        assert not submit.done()
        release.set()
        assert deletion.result(timeout=15).status_code==200
        response=submit.result(timeout=15)
        assert response.status_code==400,response.text
    assert not path.exists()
    with models.get_session() as session:
        assert session.get(models.Application,aid).status=='draft'
        assert session.get(models.Document,did) is None
        assert session.exec(select(models.Review).where(models.Review.application_id==aid)).first() is None
