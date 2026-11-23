"""Synthetic decisions traverse real auth, transactions and response serialization."""

from demo.backend.tests.review_revision_support import decision_precondition
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime
import sqlite3

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlmodel import select

from demo.backend import models
from demo.backend.main import app
from demo.backend.api import common
from demo.backend.tests.test_portal_uploads import client
from demo.backend.tests.test_db_write_failures import seed, snapshot


def fixture(client, monkeypatch):
    aid, did, original = seed(client, monkeypatch)
    with models.get_session() as session:
        row = session.get(models.Application, aid)
        row.program_code = 'job_package'
        row.status = 'submitted'
        row.submitted_at = datetime(2026, 11, 22, 12)
        session.add(row)
        other = models.Application(application_no='FAKE-UNRELATED', program_code='job_package', status='submitted')
        session.add(other); session.flush()
        session.add(models.Review(application_id=other.id, final_status='NEEDS_REVIEW', officer_memo='other memo'))
        session.commit()
    return aid, did, original


def save(client, aid, memo='합성 메모', **extra):
    return client.post(f'/api/officer/applications/{aid}/decision', json=decision_precondition(f'/api/officer/applications/{aid}/decision', {'role':'province','decision':'hold','memo':memo,**extra}))


def assert_only_human_changes(before, after, aid):
    before_rows, before_files = before
    after_rows, after_files = after
    assert before_files == after_files
    for table in before_rows:
        old, new = before_rows[table], after_rows[table]
        if table not in ('application','review'):
            assert old == new
            continue
        for a, b in zip(old, new, strict=True):
            if (a['id'] if table == 'application' else a['application_id']) != aid:
                assert a == b
            else:
                allowed = {'updated_at','status'} if table == 'application' else {'officer_role','officer_decision','officer_memo','reject_notice','decided_at','revision'}
                assert {k:v for k,v in a.items() if k not in allowed} == {k:v for k,v in b.items() if k not in allowed}


def test_memo_normal_edit_repeat_and_review_save_preserve_documents_and_other_application(client, monkeypatch):
    aid, did, original = fixture(client, monkeypatch)
    before = snapshot()
    for memo in ['첫 합성 메모','수정 합성 메모','수정 합성 메모']:
        result = save(client, aid, memo)
        assert result.status_code == 200
        detail = client.get(f'/api/officer/applications/{aid}').json()
        assert detail['decision']['memo'] == memo
        assert detail['decision']['decision'] == 'hold'
    assert_only_human_changes(before, snapshot(), aid)
    with models.get_session() as session:
        assert len(session.exec(select(models.Review).where(models.Review.application_id==aid)).all()) == 1


@pytest.mark.parametrize('failure', ['runtime500','commit503','actual-lock503'])
def test_failed_memo_has_no_partial_write_and_retry_succeeds(client, monkeypatch, failure):
    aid, did, original = fixture(client, monkeypatch)
    before = snapshot()
    def fail(connection):
        if failure == 'runtime500': raise RuntimeError('synthetic internal memo commit failure')
        underlying=sqlite3.OperationalError('synthetic private SQL')
        underlying.sqlite_errorcode=sqlite3.SQLITE_BUSY
        raise OperationalError('private SQL', {}, underlying)
    holder=None
    if failure=='actual-lock503':
        monkeypatch.setattr(models, 'SQLITE_BUSY_TIMEOUT_MS', 30)
        holder=models.engine.connect();holder.exec_driver_sql('BEGIN IMMEDIATE')
    else: event.listen(models.engine, 'commit', fail)
    try:
        with closing(TestClient(app, raise_server_exceptions=False)) as requester:
            requester.cookies.update(client.cookies)
            result=save(requester,aid)
    finally:
        if holder is not None: holder.rollback();holder.close()
        else: event.remove(models.engine, 'commit', fail)
    assert result.status_code == (500 if failure=='runtime500' else 503)
    if result.status_code == 503: assert result.headers['retry-after']=='1'
    assert 'private' not in result.text and 'RuntimeError' not in result.text
    assert snapshot()==before
    assert models._session_bind.get() is None
    assert save(client,aid).status_code == 200
    assert_only_human_changes(before, snapshot(), aid)


@pytest.mark.parametrize('actor', ['anonymous','applicant','expired','invalid-role'])
def test_memo_unauthorized_or_invalid_role_cannot_mutate(client, monkeypatch, actor):
    aid, did, original=fixture(client,monkeypatch);before=snapshot()
    with closing(TestClient(app)) as requester:
        if actor in ('applicant','expired'):requester.cookies.update(client.cookies)
        if actor=='applicant':
            for cookie in list(requester.cookies.jar):
                if 'officer' in cookie.name:requester.cookies.delete(cookie.name,domain=cookie.domain,path=cookie.path)
        if actor=='expired':monkeypatch.setenv('OFFICER_SESSION_SECRET','synthetic-other-session-key')
        if actor=='invalid-role':requester.cookies.update(client.cookies)
        result=save(requester,aid,**({'role':'applicant'} if actor=='invalid-role' else {}))
    assert result.status_code == (400 if actor=='invalid-role' else 401)
    assert snapshot()==before


def test_concurrent_decisions_reject_stale_memo_without_duplicate_review(client, monkeypatch):
    aid,did,original=fixture(client,monkeypatch);before=snapshot()
    from threading import Barrier
    barrier=Barrier(2)
    def request(memo):
        with closing(TestClient(app)) as requester:
            requester.cookies.update(client.cookies)
            body=decision_precondition(f'/api/officer/applications/{aid}/decision',{'role':'province','decision':'hold','memo':memo})
            barrier.wait(timeout=10)
            return requester.post(f'/api/officer/applications/{aid}/decision',json=body).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(request,['동시 합성 메모 A','동시 합성 메모 B']))
    assert sorted(statuses) == [200,409]
    with models.get_session() as session:
        rows=session.exec(select(models.Review).where(models.Review.application_id==aid)).all()
        assert len(rows)==1 and rows[0].revision == 2 and rows[0].officer_memo in ['동시 합성 메모 A','동시 합성 메모 B']
    assert_only_human_changes(before,snapshot(),aid)
