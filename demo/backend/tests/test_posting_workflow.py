"""Synthetic human review gates and publication state transitions."""
import pytest
from demo.backend.tests.test_postings_api import client, storage
from demo.backend.tests.test_managed_postings import create_managed


def setup(client):
    posting = create_managed(client).json()
    base = f"/api/officer/postings/{posting['id']}"
    data = client.get(base+'/workspace').json()
    return base, data


def manual_layout():
    return {'fields': {'field_name': {'type': 'text', 'field_type': 'text', 'page':0,
        'box':[20,60,170,85], 'label':'성명','required':True,'autofill_source':'name',
        'needs_review':False,'confidence':0.5}}}


def confirm_all(client, base, data):
    for row in data['forms']:
        path = base+f"/workspace/forms/{row['id']}"
        assert client.put(path+'/layout', json={'layout':manual_layout()}).status_code == 200
        response = client.post(path+'/confirm')
        assert response.status_code == 200, response.text
    return client.get(base+'/workspace').json()


def test_managed_unconfirmed_forms_never_publish(client):
    base, data = setup(client)
    refused = client.post(base+'/publish')
    assert refused.status_code == 409
    assert '확정' in refused.json()['detail']
    path = base+f"/workspace/forms/{data['forms'][0]['id']}"
    assert client.post(path+'/confirm').status_code == 409
    generated = client.post(path+'/draft')
    assert generated.status_code == 200
    assert not generated.json()['forms'][0]['confirmed']


def test_confirm_edit_invalidation_and_publication_transitions(client):
    base, data = setup(client)
    data = confirm_all(client,base,data)
    assert all(form['confirmed'] for form in data['forms'])
    assert data['publish_blockers'] == []
    published = client.post(base+'/publish')
    assert published.status_code == 200, published.text
    form = data['forms'][0]
    path = base+f"/workspace/forms/{form['id']}"
    assert client.put(path+'/layout',json={'layout':manual_layout()}).status_code == 409
    assert client.post(base+'/unpublish').json()['posting']['status'] == 'draft'
    changed = manual_layout(); changed['fields']['field_name']['label'] = '이름'
    response = client.put(path+'/layout',json={'layout':changed})
    assert response.status_code == 200
    assert not response.json()['forms'][0]['confirmed']
    assert client.post(base+'/publish').status_code == 409
    assert client.post(path+'/confirm').status_code == 200
    assert client.post(base+'/publish').status_code == 200
    assert client.post(base+'/close').json()['status'] == 'closed'


def test_review_required_fields_must_be_acknowledged_or_deleted(client):
    base, data = setup(client)
    path=base+f"/workspace/forms/{data['forms'][0]['id']}"
    layout=manual_layout(); layout['fields']['field_name']['needs_review']=True
    assert client.put(path+'/layout',json={'layout':layout}).status_code==200
    assert client.post(path+'/confirm').status_code==409
    assert client.put(path+'/layout',json={'layout':{'fields':{}}}).status_code==200
    assert client.post(path+'/confirm').status_code==409


@pytest.mark.parametrize('field,value', [('box',[-1,0,10,10]),('box',[20,20,400,300]),
    ('box',[20,20,10,10]),('page',99),('autofill_source','private_engine_key'),('field_type','unknown')])
def test_invalid_layout_cannot_be_saved(client,field,value):
    base,data=setup(client)
    path=base+f"/workspace/forms/{data['forms'][0]['id']}"
    layout=manual_layout();layout['fields']['field_name'][field]=value
    assert client.put(path+'/layout',json={'layout':layout}).status_code==422


def test_expired_period_blocks_publication(client):
    base,data=setup(client)
    confirm_all(client,base,data)
    body={'title':'FAKE expired','apply_start':'2026-01-01','apply_end':'2026-01-02','required_docs':[]}
    assert client.patch(base+'/workspace',json=body).status_code==200
    refused=client.post(base+'/publish')
    assert refused.status_code==409 and '기간' in refused.json()['detail']


def test_acroform_text_widget_draft_can_be_reviewed_and_confirmed(client):
    import pymupdf
    from demo.backend.tests.test_postings_api import NOTICE
    with pymupdf.open() as document:
        page = document.new_page(width=300, height=300)
        widget = pymupdf.Widget()
        widget.field_name = '성명'
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        widget.rect = pymupdf.Rect(40, 60, 220, 90)
        page.add_widget(widget)
        payload = document.tobytes()
    created = client.post('/api/officer/postings',data={'title':'FAKE widget','apply_start':'2026-11-10',
        'apply_end':'2026-11-20','workflow_version':'1'},files={
        'notice_pdf':('notice.pdf',NOTICE),'forms_pdf':('widget.pdf',payload)})
    assert created.status_code == 201
    base = f"/api/officer/postings/{created.json()['id']}"
    form = client.get(base+'/workspace').json()['forms'][0]
    for field in form['layout']['fields'].values():
        field['needs_review'] = False
    path = base+f"/workspace/forms/{form['id']}"
    saved = client.put(path+'/layout',json={'layout':form['layout']})
    assert saved.status_code == 200,saved.text
    assert client.post(path+'/confirm').status_code == 200
