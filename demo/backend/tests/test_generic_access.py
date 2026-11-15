"""Generic-only ownership checks use synthetic applications and PDFs."""
from fastapi.testclient import TestClient

from demo.backend.main import app
from demo.backend.tests.test_generic_programs import client,fill,pdf,publish,start


def test_generic_create_cookie_covers_api_and_owner_keeps_form_file_access(client,monkeypatch):
    posting=publish(client,['photo_1_photo'])
    created=client.post('/api/applications',json={'program_code':f'posting_{posting["id"]}'})
    assert created.status_code==200,created.text
    cookie=created.headers['set-cookie']
    assert 'Path=/api' in cookie and 'HttpOnly' in cookie and 'SameSite=lax' in cookie
    assert 'Secure' not in cookie  # TestClient uses HTTP; HTTPS is checked separately below.
    owner,form,layout=start(client,posting)
    fill(client,owner,layout)
    assert client.get(f'/api/applications/{owner["id"]}').status_code==200
    assert client.get(f'/api/applications/{owner["id"]}/forms/layouts/{form["form_no"]}').status_code==200
    result=client.post(f'/api/applications/{owner["id"]}/documents',data={'slot_key':'photo_1_photo'},
        files={'file':('synthetic.pdf',pdf(),'application/pdf')})
    assert result.status_code==200,result.text
    document_id=result.json()['document_id']
    assert client.get(f'/api/files/{document_id}').status_code==200
    assert client.get(f'/api/applications/{owner["id"]}/forms/files/written.pdf').status_code==200
    assert client.get('/api/officer/applications').status_code==200
    builtin=client.post('/api/applications',json={'program_code':'job_package'})
    assert f'Path=/api/applications/{builtin.json()["id"]}/forms/files' in builtin.headers['set-cookie']
    with TestClient(app,base_url='https://testserver') as secure:
        result=secure.post('/api/applications',json={'program_code':f'posting_{posting["id"]}'})
        assert 'Secure' in result.headers['set-cookie'] and 'Path=/api' in result.headers['set-cookie']


def test_other_applicant_cannot_read_or_mutate_generic_application_or_files(client):
    posting=publish(client,['photo_1_photo'])
    owner,form,layout=start(client,posting);fill(client,owner,layout)
    document=client.post(f'/api/applications/{owner["id"]}/documents',data={'slot_key':'photo_1_photo'},
        files={'file':('synthetic.pdf',pdf(),'application/pdf')}).json()
    base=f'/api/applications/{owner["id"]}'
    routes=[('GET',base,None),('PATCH',base,{'form1':{}}),('POST',base+'/identity',{}),
            ('GET',base+'/program',None),('GET',base+'/status',None),('GET',base+'/final-check',None),
            ('POST',base+'/submit',None),('GET',base+'/required-documents',None),('GET',base+'/documents',None),
            ('GET',base+'/forms',None),('GET',base+f'/forms/layouts/{form["form_no"]}',None),
            ('GET',base+f'/forms/{form["form_no"]}/pages/1.png',None),
            ('GET',base+f'/forms/templates/{form["form_no"]}.pdf',None),
            ('GET',base+'/forms/files/written.pdf',None),('GET',f'/api/files/{document["document_id"]}',None)]
    outsider=TestClient(app)
    other=outsider.post('/api/applications',json={'program_code':f'posting_{posting["id"]}'})
    assert other.status_code==200
    for method,url,body in routes:
        response=outsider.request(method,url,json=body)
        assert response.status_code==403,(method,url,response.text)
        assert response.json()=={'detail':'신청자 본인만 접근할 수 있습니다.'}
        assert all(value not in response.text for value in ('가상신청','합성 주소',owner['application_no'],form['title']))
        assert response.headers['cache-control']=='private, no-store'
    # Officer routes stay separate; a role-shaped header/query cannot bypass owner checks.
    assert outsider.get('/api/officer/applications').status_code==401
    assert outsider.get(base+'?role=province',headers={'Authorization':'Bearer province'}).status_code==403
    assert client.get(base).status_code==200


def test_integer_aliases_and_wrong_cookie_cannot_bypass_generic_owner_guard(client):
    posting=publish(client)
    owner,form,_=start(client,posting)
    outsider=TestClient(app)
    for alternate in (str(owner['id']),f'+{owner["id"]}',f'0{owner["id"]}',f'{owner["id"]}.0'):
        result=outsider.get(f'/api/applications/{alternate}/forms/layouts/{form["form_no"]}')
        assert result.status_code==403,(alternate,result.text)
    outsider.cookies.set(f'applicant_access_{owner["id"]}','synthetic-wrong-cookie',path='/api')
    assert outsider.get(f'/api/applications/{owner["id"]}').status_code==403
    builtin=client.post('/api/applications',json={'program_code':'job_package'}).json()
    assert outsider.get(f'/api/applications/{builtin["id"]}').status_code==403
