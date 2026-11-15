"""Officer click-to-snap suggestions on synthetic uploaded form PDFs."""
import pymupdf
from fastapi.testclient import TestClient

from demo.backend.main import app
from demo.backend.forms.draft import snap_field
from demo.backend.tests.test_postings_api import client, storage, NOTICE  # noqa: F401


def snap_pdf():
    document = pymupdf.open()
    page = document.new_page(width=500, height=500)
    for y in (40, 80):
        page.draw_line((40, y), (440, y))
    for x in (40, 160, 440):
        page.draw_line((x, 40), (x, 80))
    page.insert_text((50, 65), "은행명", fontname="korea", fontsize=11)
    page.insert_text((60, 200), "확인자 직위", fontname="korea", fontsize=11)
    page.insert_text((300, 200), "부서", fontname="korea", fontsize=11)
    page.insert_text((60, 400), "안내 문장만 있는 줄입니다", fontname="korea", fontsize=11)
    payload = document.tobytes()
    document.close()
    return payload


def upload(client):
    response = client.post('/api/officer/postings', data={'title': 'FAKE 칸 맞춤', 'apply_start': '2026-11-10',
        'apply_end': '2026-11-20', 'workflow_version': '1'}, files={
        'notice_pdf': ('notice.pdf', NOTICE), 'forms_pdf': ('synthetic.pdf', snap_pdf())})
    assert response.status_code == 201, response.text
    base = f"/api/officer/postings/{response.json()['id']}"
    form_id = client.get(base + '/workspace').json()['forms'][0]['id']
    return base, form_id


def test_snap_fits_blank_table_cell_with_left_label():
    suggestion = snap_field(snap_pdf(), 0, 300, 60)
    assert suggestion == {"box": [162.0, 42.0, 438.0, 78.0], "field_type": "text", "label": "은행명"}


def test_snap_fits_inline_blank_between_words():
    suggestion = snap_field(snap_pdf(), 0, 200, 195)
    assert suggestion is not None and suggestion["label"] == "확인자 직위"
    left, top, right, bottom = suggestion["box"]
    assert 120 < left < 200 < right < 300 and top < 195 < bottom


def test_snap_without_target_returns_none():
    assert snap_field(snap_pdf(), 0, 250, 300) is None
    assert snap_field(snap_pdf(), 0, 100, 395) is None  # inside printed words, no blank


def test_snap_route_requires_officer_session(client):
    base, form_id = upload(client)
    stranger = TestClient(app)
    response = stranger.post(f'{base}/workspace/forms/{form_id}/snap', json={'page': 0, 'x': 300, 'y': 60})
    assert response.status_code == 401


def test_snap_route_answers_box_or_null_and_hides_other_postings(client):
    base, form_id = upload(client)
    path = f'{base}/workspace/forms/{form_id}/snap'
    fitted = client.post(path, json={'page': 0, 'x': 300, 'y': 60})
    assert fitted.status_code == 200 and fitted.json()['label'] == '은행명'
    assert set(fitted.json()) == {'box', 'field_type', 'label'}
    assert client.post(path, json={'page': 0, 'x': 250, 'y': 300}).json() == {'box': None}
    assert client.post(path, json={'page': 3, 'x': 1, 'y': 1}).status_code == 422
    other, _ = upload(client)
    assert client.post(f'{other}/workspace/forms/{form_id}/snap', json={'page': 0, 'x': 1, 'y': 1}).status_code == 404
    assert client.post(f'{base}/workspace/forms/999999/snap', json={'page': 0, 'x': 1, 'y': 1}).status_code == 404
    assert client.post('/api/officer/postings/999999/workspace/forms/1/snap',
                       json={'page': 0, 'x': 1, 'y': 1}).status_code == 404
    layout = client.get(base + '/workspace').json()['forms'][0]['layout']
    assert all(field['needs_review'] for field in layout['fields'].values())
