"""Single-choice circle marks for printed choice words (rule a), end to end.

Every PDF is synthetic and generated here with PyMuPDF; no fixture file is read.
"""
from copy import deepcopy
import json

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine

from demo.backend import models
from demo.backend.api import applications, common, documents, files, forms, postings
from demo.backend.forms.coords import FormCoords
from demo.backend.forms.draft import draft_layout
from demo.backend.forms.render import circle_mark_rect, render
from demo.backend.forms.values import FilledForm
from demo.backend.main import app
from demo.backend.tests.security_support import authenticate_officer
from demo.backend.tests.test_generic_programs import TODAY, signature


def _choice_pdf() -> bytes:
    with pymupdf.open() as document:
        page = document.new_page(width=500, height=400)
        page.insert_text((40, 100), "1. 해당 지역에 거주합니까?", fontname="korea", fontsize=11)
        page.insert_text((360, 100), "예,", fontname="korea", fontsize=11)
        page.insert_text((390, 100), "아니오", fontname="korea", fontsize=11)
        return document.tobytes()


def _ovals(page) -> list[pymupdf.Rect]:
    """Stroked, unfilled curve paths: the circle marks."""
    return [pymupdf.Rect(path["rect"]) for path in page.get_drawings()
            if path.get("fill") is None and any(item[0] == "c" for item in path["items"])]


def _filled(page) -> list[pymupdf.Rect]:
    return [pymupdf.Rect(path["rect"]) for path in page.get_drawings() if path.get("fill") is not None]


# Drafting ------------------------------------------------------------------------------

def test_choice_word_pair_is_one_radio_group_with_circle_marks():
    layout = draft_layout(_choice_pdf())
    choices = [field for field in layout["fields"].values() if field.get("choice_mark")]
    assert [field["label"] for field in choices] == ["예", "아니오"]
    assert {field["field_type"] for field in choices} == {"radio"}
    assert {field["type"] for field in choices} == {"check"}
    assert choices[0]["group"] == choices[1]["group"]
    assert {field["choice_mark"] for field in choices} == {"circle"}
    assert all(field["needs_review"] for field in layout["fields"].values()) and not layout["confirmed"]


def test_printed_boxes_stay_plain_checks_without_circle_marks():
    with pymupdf.open() as document:
        page = document.new_page(width=500, height=400)
        for x, word in ((300, "예"), (360, "아니오")):
            page.draw_rect(pymupdf.Rect(x, 90, x + 10, 100))
            page.insert_text((x + 14, 100), word, fontname="korea", fontsize=11)
        fields = list(draft_layout(document.tobytes())["fields"].values())
    assert len(fields) == 2
    assert all(field["field_type"] == "check" and "choice_mark" not in field for field in fields)


# Rendering -----------------------------------------------------------------------------

def _coords(tmp_path, fields) -> FormCoords:
    template = tmp_path / "template.pdf"
    with pymupdf.open() as document:
        document.new_page(width=300, height=200)
        document.save(template)
    return FormCoords(form_no="synthetic", title="합성", template=template, fields=fields, source={})


def test_circle_mark_surrounds_only_the_chosen_word(tmp_path):
    word = {"type": "check", "field_type": "radio", "page": 0, "group": "g", "choice_mark": "circle"}
    coords = _coords(tmp_path, {"yes": {**word, "box": [100, 50, 112, 62]},
                                "no": {**word, "box": [140, 50, 170, 62]}})
    with pymupdf.open(stream=render(coords, FilledForm(form_no="synthetic", checks=["no"])), filetype="pdf") as pdf:
        ovals, filled = _ovals(pdf[0]), _filled(pdf[0])
    assert len(ovals) == 1 and filled == []
    oval = ovals[0]
    assert oval.contains(pymupdf.Rect(140, 50, 170, 62))  # the whole word stays inside, uncovered
    assert oval.x0 > 112  # the other word is not circled
    expected = circle_mark_rect([140, 50, 170, 62])
    assert [round(value) for value in oval] == [round(value) for value in expected]


def test_plain_box_check_still_draws_the_filled_check(tmp_path):
    coords = _coords(tmp_path, {"box": {"type": "check", "field_type": "check", "page": 0, "box": [100, 50, 110, 60]}})
    with pymupdf.open(stream=render(coords, FilledForm(form_no="synthetic", checks=["box"])), filetype="pdf") as pdf:
        assert _ovals(pdf[0]) == [] and len(_filled(pdf[0])) == 1


def test_circle_mark_padding_matches_the_applicant_screen_formula():
    # Same constants as src/lib/form-choice.ts circleMarkBox.
    assert circle_mark_rect([0, 0, 30, 10]) == (-3.5, -3.0, 33.5, 13.0)
    assert circle_mark_rect([0, 0, 30, 4]) == (-2.0, -1.5, 32.0, 5.5)


# Officer layout, applicant choice, required group, submitted PDF ------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path / "synthetic.db"}', connect_args={'check_same_thread': False})
    monkeypatch.setattr(models, 'engine', engine)
    storage = tmp_path / 'storage'
    for module in (applications, common, documents, files, forms, postings):
        monkeypatch.setattr(module, 'STORAGE', storage)
    monkeypatch.setattr(applications, 'SIGNATURES', storage / 'signatures')
    monkeypatch.setattr(documents, 'DOCUMENTS', storage / 'documents')
    monkeypatch.setattr(models, 'posting_today', lambda: TODAY)
    monkeypatch.setenv('ENGINE_V2_OCR', 'off')
    with TestClient(app) as connected:
        authenticate_officer(connected, monkeypatch)
        yield connected
    engine.dispose()


def _published(client, *, required: bool):
    created = client.post('/api/officer/postings', data={
        'title': '합성 선택 사업', 'apply_start': '2026-11-01', 'apply_end': '2026-12-01',
        'workflow_version': '1', 'required_docs': '[]'},
        files={'notice_pdf': ('notice.pdf', _choice_pdf(), 'application/pdf'),
               'forms_pdf': ('choice.pdf', _choice_pdf(), 'application/pdf')})
    assert created.status_code == 201, created.text
    base = f'/api/officer/postings/{created.json()["id"]}'
    form_id = client.get(base + '/workspace').json()['forms'][0]['id']
    drafted = client.post(base + f'/workspace/forms/{form_id}/draft')
    assert drafted.status_code == 200, drafted.text
    layout = drafted.json()['forms'][0]['layout']
    radios = {key for key, field in layout['fields'].items() if field.get('choice_mark') == 'circle'}
    assert len(radios) == 2
    layout['fields'] = {key: {**field, 'required': required, 'needs_review': False}
                        for key, field in layout['fields'].items() if key in radios}
    saved = client.put(base + f'/workspace/forms/{form_id}/layout', json={'layout': layout})
    assert saved.status_code == 200, saved.text
    kept = saved.json()['forms'][0]['layout']['fields']
    assert {field.get('choice_mark') for field in kept.values()} == {'circle'}
    assert client.post(base + f'/workspace/forms/{form_id}/confirm').status_code == 200
    published = client.post(base + '/publish')
    assert published.status_code == 200, published.text
    return published.json()


def _applicant(client, posting):
    row = client.post('/api/applications', json={'program_code': f'posting_{posting["id"]}'}).json()
    result = client.post(f'/api/applications/{row["id"]}/identity', json={
        'name': '가상신청', 'birth': '2000-05-15', 'phone': '01012345678', 'pledge': True,
        'signature_kind': 'electronic', 'signature_data_url': signature()})
    assert result.status_code == 200, result.text
    form_no = client.get(f'/api/applications/{row["id"]}/forms').json()[0]['form_no']
    layout = client.get(f'/api/applications/{row["id"]}/forms/layouts/{form_no}').json()
    by_label = {field['label']: key for key, field in layout['fields'].items()}
    return row, form_no, layout, by_label['예'], by_label['아니오']


def test_required_choice_group_blocks_until_one_word_is_chosen_and_switching_clears_the_other(client):
    row, form_no, layout, yes, no = _applicant(client, _published(client, required=True))
    assert {layout['fields'][key]['choice_mark'] for key in (yes, no)} == {'circle'}
    assert layout['fields'][yes]['group'] == layout['fields'][no]['group']
    path = f'/api/applications/{row["id"]}'
    final = client.get(path + '/final-check').json()
    assert not final['can_submit']
    assert {issue.get('target') for issue in final['blockers']} >= {yes, no}
    assert client.patch(path, json={'form1': {yes: True, no: True}}).status_code == 422
    assert client.patch(path, json={'form1': {yes: True}}).status_code == 200
    assert client.get(path + '/final-check').json()['can_submit']
    # Switching sends the new choice with the old one cleared, as the applicant screen does.
    assert client.patch(path, json={'form1': {yes: False, no: True}}).status_code == 200
    stored = client.get(path).json()['form1_json']
    assert stored[yes] is False and stored[no] is True
    assert client.get(path + '/final-check').json()['can_submit']
    with pymupdf.open(stream=client.get(f'{path}/forms/{form_no}.pdf').content, filetype='pdf') as pdf:
        ovals = _ovals(pdf[0])
    assert len(ovals) == 1 and ovals[0].contains(pymupdf.Rect(layout['fields'][no]['box']))
    assert not ovals[0].intersects(pymupdf.Rect(layout['fields'][yes]['box']))


def test_optional_choice_group_does_not_block(client):
    row, _, _, _, _ = _applicant(client, _published(client, required=False))
    assert client.get(f'/api/applications/{row["id"]}/final-check').json()['can_submit']


def test_layout_rejects_unknown_choice_marks_and_drops_them_on_non_choice_fields(client):
    from demo.backend.api.posting_workflow import validate_layout
    from demo.backend.api import posting_workspace

    created = client.post('/api/officer/postings', data={
        'title': '합성 검증 사업', 'apply_start': '2026-11-01', 'apply_end': '2026-12-01',
        'workflow_version': '1', 'required_docs': '[]'},
        files={'notice_pdf': ('notice.pdf', _choice_pdf(), 'application/pdf'),
               'forms_pdf': ('choice.pdf', _choice_pdf(), 'application/pdf')})
    row = posting_workspace.form_rows(created.json()['id'])[0]
    base = {'type': 'check', 'field_type': 'radio', 'page': 0, 'box': [10, 10, 30, 22], 'label': '예', 'group': 'g'}
    clean = validate_layout(row, {'fields': {'a': {**base, 'choice_mark': 'circle'},
                                             'b': {**base, 'type': 'text', 'field_type': 'text', 'choice_mark': 'circle'},
                                             'c': deepcopy(base)}})['fields']
    assert clean['a']['choice_mark'] == 'circle'
    assert 'choice_mark' not in clean['b'] and 'choice_mark' not in clean['c']
    with pytest.raises(Exception) as error:
        validate_layout(row, {'fields': {'a': {**base, 'choice_mark': 'square'}}})
    assert getattr(error.value, 'status_code', None) == 422
    assert json.dumps(clean, ensure_ascii=False).count('circle') == 1
