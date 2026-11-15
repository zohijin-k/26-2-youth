"""Synthetic uploaded forms get review-required layouts before any publishing."""
from demo.backend.tests.test_postings_api import client, storage, NOTICE
from demo.backend.tests.test_form_draft import synthetic_table


def test_upload_automatically_drafts_and_regeneration_never_confirms(client):
    with synthetic_table() as pdf:
        payload = pdf.tobytes()
    response = client.post('/api/officer/postings',data={'title':'FAKE 자동 서식','apply_start':'2026-11-10',
        'apply_end':'2026-11-20','workflow_version':'1'},files={
        'notice_pdf':('notice.pdf',NOTICE),'forms_pdf':('synthetic.pdf',payload)})
    assert response.status_code == 201,response.text
    base=f"/api/officer/postings/{response.json()['id']}"
    workspace=client.get(base+'/workspace').json()
    row=workspace['forms'][0]
    assert row['layout']['fields']
    assert all(field['needs_review'] for field in row['layout']['fields'].values())
    assert not row['confirmed']
    assert client.post(base+'/publish').status_code == 409
    refreshed=client.post(base+f"/workspace/forms/{row['id']}/draft")
    assert refreshed.status_code==200,refreshed.text
    assert not refreshed.json()['forms'][0]['confirmed']
    assert client.post(base+'/publish').status_code==409


def test_draft_route_enforces_posting_ownership(client):
    builtin=client.get('/api/officer/postings').json()['items'][0]
    assert client.post(f"/api/officer/postings/{builtin['id']}/workspace/forms/999/draft").status_code==409
    assert client.post('/api/officer/postings/999/workspace/forms/999/draft').status_code==404
