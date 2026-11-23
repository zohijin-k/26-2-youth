"""Synthetic published-program API flow, isolation and conservative decisions."""

from demo.backend.tests.review_revision_support import decision_precondition
from copy import deepcopy
from datetime import date
import base64
import json

import pymupdf
import pytest
from fastapi.testclient import TestClient
from demo.backend.tests.security_support import authenticate_officer
from sqlmodel import create_engine,select

from demo.backend import models
from demo.backend.api import applications,common,documents,files,forms,postings
from demo.backend.main import app
from demo.backend.ocr.base import OcrResult
from demo.backend.rules.doc_types import DocType

TODAY=date(2026,11,15)


def pdf(table=False):
    with pymupdf.open() as document:
        page=document.new_page(width=500,height=400)
        page.insert_text((40,30),'SYNTHETIC PUBLIC FORM')
        if table:
            for y in (60,100,140):page.draw_line((40,y),(450,y))
            for x in (40,160,450):page.draw_line((x,60),(x,140))
            for y,label in ((85,'성명'),(125,'주소')):page.insert_text((50,y),label,fontname='korea',fontsize=11)
        return document.tobytes()


def signature():
    image=pymupdf.Pixmap(pymupdf.csRGB,pymupdf.IRect(0,0,32,20),False)
    image.clear_with(230)
    return 'data:image/png;base64,'+base64.b64encode(image.tobytes('png')).decode()


@pytest.fixture
def client(tmp_path,monkeypatch):
    engine=create_engine(f'sqlite:///{tmp_path / "synthetic.db"}',connect_args={'check_same_thread':False})
    monkeypatch.setattr(models,'engine',engine)
    storage=tmp_path/'storage'
    for module in (applications,common,documents,files,forms,postings):monkeypatch.setattr(module,'STORAGE',storage)
    monkeypatch.setattr(applications,'SIGNATURES',storage/'signatures')
    monkeypatch.setattr(documents,'DOCUMENTS',storage/'documents')
    monkeypatch.setattr(models,'posting_today',lambda:TODAY)
    monkeypatch.setenv('ENGINE_V2_OCR','off')
    with TestClient(app) as connected:
        authenticate_officer(connected, monkeypatch)
        yield connected
    engine.dispose()


def managed(client,docs=None):
    result=client.post('/api/officer/postings',data={'title':'합성 공개 사업','apply_start':'2026-11-01','apply_end':'2026-12-01',
        'workflow_version':'1','required_docs':json.dumps(docs or [])},files={'notice_pdf':('notice.pdf',pdf(),'application/pdf'),
            'forms_pdf':('form.pdf',pdf(True),'application/pdf')})
    assert result.status_code==201,result.text
    return result.json()


def publish(client,docs=None):
    posting=managed(client,docs)
    base=f'/api/officer/postings/{posting["id"]}'
    workspace=client.get(base+'/workspace').json()
    field_form=workspace['forms'][0]
    result=client.post(base+f'/workspace/forms/{field_form["id"]}/draft')
    assert result.status_code==200,result.text
    layout=result.json()['forms'][0]['layout']
    assert layout['fields']
    for field in layout['fields'].values():field.update(required=True,needs_review=False)
    result=client.put(base+f'/workspace/forms/{field_form["id"]}/layout',json={'layout':layout})
    assert result.status_code==200,result.text
    assert client.post(base+f'/workspace/forms/{field_form["id"]}/confirm').status_code==200
    result=client.post(base+'/publish')
    assert result.status_code==200,result.text
    return result.json()


def start(client,posting):
    result=client.post('/api/applications',json={'program_code':f'posting_{posting["id"]}'})
    assert result.status_code==200,result.text
    row=result.json()
    result=client.post(f'/api/applications/{row["id"]}/identity',json={'name':'가상신청','birth':'2000-05-15',
        'phone':'01012345678','pledge':True,'signature_kind':'electronic','signature_data_url':signature()})
    assert result.status_code==200,result.text
    listing=client.get(f'/api/applications/{row["id"]}/forms').json()
    layout=client.get(f'/api/applications/{row["id"]}/forms/layouts/{listing[0]["form_no"]}').json()
    return row,listing[0],layout


def fill(client,row,layout):
    body={key:'합성 주소' for key,field in layout['fields'].items() if not field.get('readonly')}
    result=client.patch(f'/api/applications/{row["id"]}',json={'form1':body})
    assert result.status_code==200,result.text
    return result.json()


def test_published_program_end_to_end_uses_snapshot_and_officer_pass_queue(client,monkeypatch):
    posting=publish(client,['photo_1_photo'])
    assert posting['can_apply'] and posting['apply_path']==f'/apply/programs/{posting["id"]}/identity'
    row,listing,layout=start(client,posting)
    assert all(key.startswith('p') and '_f' in key for key in layout['fields'])
    assert all('confidence' not in field and 'anchor' not in field for field in layout['fields'].values())
    fill(client,row,layout)
    monkeypatch.setattr(documents,'read_document',lambda path,expected:OcrResult(detected_doc_type=DocType.ID_PHOTO_COPY,
        confidence=.99,image_quality=1,issue_date=TODAY, fields={'발급일': TODAY.isoformat()},tier='synthetic',engine='synthetic'))
    upload=client.post(f'/api/applications/{row["id"]}/documents',data={'slot_key':'photo_1_photo'},
        files={'file':('renamed.pdf',pdf(),'application/pdf')})
    assert upload.status_code==200,upload.text
    assert upload.json()['status']=='PASS',upload.json()
    final=client.get(f'/api/applications/{row["id"]}/final-check')
    assert final.status_code==200 and final.json()['can_submit'],final.text
    assert final.json()['first_come'] is None and final.json()['subsidy'] is None
    result=client.post(f'/api/applications/{row["id"]}/submit')
    assert result.status_code==200,result.text
    assert result.json()['status']=='submitted'
    written=client.get(f'/api/applications/{row["id"]}/forms/files/written.pdf')
    assert written.status_code==200 and written.content.startswith(b'%PDF-')
    with pymupdf.open(stream=written.content,filetype='pdf') as document:assert document.page_count==1
    officer=client.get('/api/officer/applications',params={'program':f'posting_{posting["id"]}','queue':'pass'}).json()
    assert officer['total']==1 and officer['queues']=={'needs_check':0,'pass':1,'done':0}
    counts=client.get(f'/api/officer/postings/{posting["id"]}').json()
    assert counts['application_count']==1 and counts['needs_check_count']==0
    reasons=client.get(f'/api/officer/applications/{row["id"]}/reasons')
    assert reasons.status_code==200 and '자격 규칙 미설정' in reasons.json()['program_notice']
    assert client.get(f'/api/officer/applications/{row["id"]}').status_code==409


@pytest.mark.parametrize('state',['draft','closed','future','expired','unconfirmed'])
def test_generic_create_guards_without_creating_empty_applications(client,state):
    posting=publish(client) if state!='draft' else managed(client)
    with models.get_session() as session:
        stored=session.get(models.ProgramPosting,posting['id'])
        if state=='closed':stored.status='closed'
        if state=='future':stored.apply_start=date(2026,11,16)
        if state=='expired':stored.apply_end=date(2026,11,14)
        if state=='unconfirmed':
            field=session.exec(select(models.ProgramForm).where(models.ProgramForm.posting_id==posting['id'])).first()
            field.confirmed_hash=None;session.add(field)
        session.add(stored);session.commit()
    result=client.post('/api/applications',json={'program_code':f'posting_{posting["id"]}'})
    assert result.status_code==409,result.text
    with models.get_session() as session:assert session.exec(select(models.Application)).all()==[]


def test_required_fields_identity_lock_and_rrn_redaction(client):
    posting=publish(client)
    row,listing,layout=start(client,posting)
    check=client.get(f'/api/applications/{row["id"]}/final-check').json()
    assert any(item['kind']=='form' for item in check['blockers'])
    name_key=next(key for key,field in layout['fields'].items() if field.get('autofill_source')=='name')
    address_key=next(key for key,field in layout['fields'].items() if not field.get('readonly'))
    patched=client.patch(f'/api/applications/{row["id"]}',json={'form1':{name_key:'다른이름',address_key:'합성 000515-3123456',
        'internal_engine':'must be dropped','account':'must be dropped'}})
    assert patched.status_code==200,patched.text
    data=patched.json()
    assert data['form1_json'][name_key]=='가상신청'
    assert 'internal_engine' not in data['form1_json'] and 'account' not in data['form1_json']
    assert '123456' not in patched.text
    assert 'pledge_signature_path' not in patched.text
    assert client.get(f'/api/applications/{row["id"]}/final-check').json()['can_submit']
    assert client.get(f'/api/applications/{row["id"]}/program').json()['title']=='합성 공개 사업'


def test_unreadable_documents_route_to_review_and_bulk_approval_is_blocked(client,monkeypatch):
    posting=publish(client,['photo_1_photo'])
    row,listing,layout=start(client,posting);fill(client,row,layout)
    monkeypatch.setattr(documents,'read_document',lambda path,expected:OcrResult(tier='none'))
    upload=client.post(f'/api/applications/{row["id"]}/documents',data={'slot_key':'photo_1_photo'},files={'file':('same.pdf',pdf(),'application/pdf')})
    assert upload.status_code==200,upload.text
    assert upload.json()['status']=='NEEDS_REVIEW',upload.json()
    result=client.post(f'/api/applications/{row["id"]}/submit')
    assert result.status_code==200,result.text
    officer=client.get('/api/officer/applications',params={'program':f'posting_{posting["id"]}','queue':'needs_check'}).json()
    assert officer['total']==1
    bulk=client.post('/api/officer/applications/decisions',json=decision_precondition('/api/officer/applications/decisions', {'role':'province','decision':'approve','application_ids':[row['id']]}))
    assert bulk.status_code in (400,409),bulk.text


def test_confirmed_document_fail_remains_submission_blocker(client,monkeypatch):
    posting=publish(client,['photo_1_photo'])
    row,listing,layout=start(client,posting);fill(client,row,layout)
    monkeypatch.setattr(documents,'read_document',lambda path,expected:OcrResult(detected_doc_type=DocType.RESIDENT_CERTIFICATE,
        confidence=.99,image_quality=1,issue_date=TODAY, fields={'발급일': TODAY.isoformat()},tier='synthetic'))
    upload=client.post(f'/api/applications/{row["id"]}/documents',data={'slot_key':'photo_1_photo'},files={'file':('photo.pdf',pdf(),'application/pdf')})
    assert upload.json()['status']=='FAIL',upload.json()
    assert not client.get(f'/api/applications/{row["id"]}/final-check').json()['can_submit']
    assert client.post(f'/api/applications/{row["id"]}/submit').status_code==400


def test_snapshot_survives_posting_changes_and_templates_are_application_owned(client):
    posting=publish(client)
    row,listing,layout=start(client,posting);fill(client,row,layout)
    original=client.get(f'/api/applications/{row["id"]}/forms/templates/{listing["form_no"]}.pdf').content
    with models.get_session() as session:
        stored=session.get(models.ProgramPosting,posting['id']);stored.title='합성 바뀐 사업';stored.guidance_text='수정 안내'
        form=session.exec(select(models.ProgramForm).where(models.ProgramForm.posting_id==posting['id'])).first()
        form.layout_json={};session.add(form);session.add(stored);session.commit()
    assert client.get(f'/api/applications/{row["id"]}/program').json()['title']=='합성 공개 사업'
    assert client.get(f'/api/applications/{row["id"]}/forms/layouts/{listing["form_no"]}').json()==layout
    assert client.get(f'/api/applications/{row["id"]}/forms/templates/{listing["form_no"]}.pdf').content==original
    assert client.get(f'/api/applications/{row["id"]}/forms/{listing["form_no"]}/pages/1.png?dpi=60').status_code==200
    assert client.get(f'/api/applications/{row["id"]}/forms/{listing["form_no"]}/pages/1.png?dpi=60&preview=true').status_code==200


def test_multiple_forms_have_distinct_keys_and_two_page_combined_archive(client):
    result=client.post('/api/officer/postings',data={'title':'합성 여러 서식','apply_start':'2026-11-01','apply_end':'2026-12-01',
        'workflow_version':'1','required_docs':'[]'},files=[('notice_pdf',('notice.pdf',pdf(),'application/pdf')),
            ('forms_pdf',('form-one.pdf',pdf(True),'application/pdf')),('forms_pdfs',('form-two.pdf',pdf(True),'application/pdf'))])
    posting=result.json();base=f'/api/officer/postings/{posting["id"]}'
    workspace=client.get(base+'/workspace').json()
    for field_form in workspace['forms']:
        draft=client.post(base+f'/workspace/forms/{field_form["id"]}/draft').json()
        layout=next(row['layout'] for row in draft['forms'] if row['id']==field_form['id'])
        for field in layout['fields'].values():field.update(required=False,needs_review=False)
        assert client.put(base+f'/workspace/forms/{field_form["id"]}/layout',json={'layout':layout}).status_code==200
        assert client.post(base+f'/workspace/forms/{field_form["id"]}/confirm').status_code==200
    assert client.post(base+'/publish').status_code==200
    row,_,_=start(client,posting)
    listing=client.get(f'/api/applications/{row["id"]}/forms').json()
    layouts=[client.get(f'/api/applications/{row["id"]}/forms/layouts/{item["form_no"]}').json() for item in listing]
    assert set(layouts[0]['fields']).isdisjoint(layouts[1]['fields'])
    assert client.post(f'/api/applications/{row["id"]}/submit').status_code==200
    written=client.get(f'/api/applications/{row["id"]}/forms/files/written.pdf')
    with pymupdf.open(stream=written.content,filetype='pdf') as document:assert document.page_count==2


def test_radio_single_choice_and_signature_input_validation(client):
    posting=publish(client)
    with models.get_session() as session:
        field_form=session.exec(select(models.ProgramForm).where(models.ProgramForm.posting_id==posting['id'])).first()
        stored=deepcopy(field_form.layout_json)
        first=next(iter(stored['fields'].values()))
        second=deepcopy(first)
        first.update(type='check',field_type='radio',group='private_internal_group',autofill_source=None)
        second.update(type='check',field_type='radio',group='private_internal_group',autofill_source=None)
        third=deepcopy(first);third.update(type='image',field_type='signature',group='',required=False)
        stored['fields']={'option_a':first,'option_b':second,'signature':third}
        field_form.layout_json=stored
        from demo.backend.api.posting_workflow import layout_hash
        field_form.confirmed_hash=layout_hash(stored)
        session.add(field_form);session.commit()
    row,_,layout=start(client,posting)
    radios=[key for key,field in layout['fields'].items() if field['field_type']=='radio']
    assert len(radios)==2
    assert all(layout['fields'][key]['group'].startswith('p') for key in radios)
    assert 'private_internal_group' not in json.dumps(layout)
    assert client.patch(f'/api/applications/{row["id"]}',json={'form1':{key:True for key in radios}}).status_code==422
    assert client.patch(f'/api/applications/{row["id"]}',json={'form1':{radios[0]:True}}).status_code==200
    assert client.get(f'/api/applications/{row["id"]}/final-check').json()['can_submit']
    sign=next(key for key,field in layout['fields'].items() if field['field_type']=='signature')
    assert client.patch(f'/api/applications/{row["id"]}',json={'form1':{sign:'data:image/png;base64,bm90LWFuLWltYWdl'}}).status_code==422
    assert client.patch(f'/api/applications/{row["id"]}',json={'form1':{sign:signature(),radios[0]:True}}).status_code==200


def test_checklist_program_metadata_is_nested_and_complete(client):
    posting=publish(client,['photo_1_photo'])
    row,_,_=start(client,posting)
    response=client.get(f'/api/applications/{row["id"]}/required-documents')
    assert response.status_code==200,response.text
    body=response.json()
    assert {'code','name','selection','allows_supplement','supplement_days','document_cutoff','announcement_date',
            'application_period','application_period_2','asks_work_category','has_subsidy_items','paper_forms'} <= set(body['program'])
    assert body['program']['selection']=='manual'
    assert not body['program']['asks_work_category'] and not body['program']['has_subsidy_items']
    assert not ({'application_period_2','asks_work_category','has_subsidy_items','paper_forms'} & set(body))


@pytest.mark.parametrize('change',['close','unpublish','remove','future','expired'])
def test_existing_draft_cannot_submit_after_current_program_stops_accepting(client,change):
    posting=publish(client)
    row,_,layout=start(client,posting);fill(client,row,layout)
    assert client.get(f'/api/applications/{row["id"]}/final-check').json()['can_submit']
    if change in ('close','unpublish'):
        result=client.post(f'/api/officer/postings/{posting["id"]}/{change}')
        assert result.status_code==200,result.text
    else:
        with models.get_session() as session:
            stored=session.get(models.ProgramPosting,posting['id'])
            if change=='remove':session.delete(stored)
            elif change=='future':stored.apply_start=date(2026,11,16);session.add(stored)
            elif change=='expired':stored.apply_end=date(2026,11,14);session.add(stored)
            session.commit()
    final=client.get(f'/api/applications/{row["id"]}/final-check')
    assert final.status_code==200,final.text
    assert not final.json()['can_submit']
    blocker=next(item for item in final.json()['blockers'] if item.get('code')=='PROGRAM_NOT_OPEN')
    assert blocker['message']=='현재 접수 중인 사업이 아닙니다. 사업 안내를 확인해 주세요.'
    assert client.post(f'/api/applications/{row["id"]}/submit').status_code==400
    listing=client.get(f'/api/applications/{row["id"]}/forms').json()
    assert client.get(f'/api/applications/{row["id"]}/forms/layouts/{listing[0]["form_no"]}').status_code==200


@pytest.mark.parametrize('change',['close','unpublish','remove'])
def test_submitted_archive_remains_available_after_program_stops_accepting(client,change):
    posting=publish(client)
    row,listing,layout=start(client,posting);fill(client,row,layout)
    assert client.post(f'/api/applications/{row["id"]}/submit').status_code==200
    original=client.get(f'/api/applications/{row["id"]}/forms/files/written.pdf')
    assert original.status_code==200
    if change in ('close','unpublish'):
        assert client.post(f'/api/officer/postings/{posting["id"]}/{change}').status_code==200
    else:
        with models.get_session() as session:
            session.delete(session.get(models.ProgramPosting,posting['id']));session.commit()
    archived=client.get(f'/api/applications/{row["id"]}/forms/files/written.pdf')
    assert archived.status_code==200 and archived.content==original.content
    assert client.get(f'/api/applications/{row["id"]}/status').status_code==200
    assert client.get(f'/api/applications/{row["id"]}/forms/templates/{listing["form_no"]}.pdf').status_code==200
