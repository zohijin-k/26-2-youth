"""Provider egress contains public posting facts and canonical rules only."""
import json
from demo.backend import llm_drafts, models
from demo.backend.tests.test_postings_api import client, storage
from demo.backend.tests.test_managed_postings import create_managed


class Spy:
    name = 'fake'
    def __init__(self): self.calls = []
    def generate(self, purpose, payload):
        self.calls.append((purpose, payload))
        return '합성 자동 설명'


def test_guidance_endpoint_uses_only_public_posting_and_notice(client,monkeypatch):
    spy=Spy();monkeypatch.setattr(llm_drafts,'configured_provider',lambda:spy)
    row=create_managed(client).json()
    response=client.post(f"/api/officer/postings/{row['id']}/workspace/guidance-draft",
        json={'name':'FAKE secret applicant','account':'FAKE secret account','prompt':'FAKE injected prompt'})
    assert response.status_code==200,response.text
    assert response.json()['source']=='fake'
    purpose,payload=spy.calls[0]
    assert purpose=='guidance'
    assert set(payload)=={'title','apply_start','apply_end','documents','notice_text'}
    assert payload['title']=='FAKE 관리형 사업'
    assert 'FAKE notice' in payload['notice_text']
    assert 'secret' not in json.dumps(payload)
    assert 'injected' not in json.dumps(payload)


def test_reason_endpoint_reconstructs_canonical_rules_without_personal_values(client,monkeypatch):
    spy=Spy();monkeypatch.setattr(llm_drafts,'configured_provider',lambda:spy)
    row=client.post('/api/applications',json={'program_code':'job_package'}).json()
    with models.get_session() as session:
        app=session.get(models.Application,row['id'])
        app.status='submitted';app.form1_json={'name':'FAKE_PERSON_SECRET','accountNo':'FAKE_ACCOUNT_SECRET'}
        session.add(app)
        session.add(models.Review(application_id=app.id,final_status='NEEDS_REVIEW'))
        session.add(models.Document(application_id=app.id,slot_key='resident_abstract',file_path='unused-synthetic',
            file_format='pdf',stage1_status='NEEDS_REVIEW',ocr_json={'fields':{'name':'FAKE_OCR_SECRET'}},
            findings_json=[{'code':'IDENTITY_UNCERTAIN','message':'FAKE_PERSON_SECRET FAKE_ACCOUNT_SECRET',
                'severity':'NEEDS_REVIEW'},{'code':'FAKE_PERSON_SECRET','message':'FAKE_OCR_SECRET','severity':'NEEDS_REVIEW'}]))
        session.commit()
    response=client.get(f"/api/officer/applications/{row['id']}/reason-explanation?role=province")
    assert response.status_code==200,response.text
    assert response.json()['label']=='설명(자동 작성)'
    purpose,payload=spy.calls[0]
    assert purpose=='review' and set(payload)=={'rules'}
    serialized=json.dumps(payload,ensure_ascii=False)
    assert all(secret not in serialized for secret in ('FAKE_PERSON_SECRET','FAKE_ACCOUNT_SECRET','FAKE_OCR_SECRET'))
    assert any(rule['code']=='IDENTITY_UNCERTAIN' for rule in payload['rules'])
    assert all(set(rule)=={'code','field_names','rule_text'} for rule in payload['rules'])
