"""Actual resident image-PDF uploads preserve note numbering and review gaps."""
import io

import pymupdf
import pytest
from PIL import Image

from demo.backend.ocr import read_document
from demo.backend.ocr.localocr import LocalOcr
from demo.backend.rules.doc_types import DocType
from demo.backend.tests.test_portal_uploads import client, new_app, upload
from engine_v2.pipeline import ocr as coordinate_ocr
from engine_v2.tests import p2_resident_samples as sample
from .scan_guard import scan_guard_off  # noqa: F401 (fixture; the guard itself: test_resident_scan_guard.py)
from engine_v2.tests.test_p2_resident import _without_row


def image_pdf(path, pages):
    content = io.BytesIO()
    Image.new("RGB", pages[0][0].pixel_size, "white").save(content, format="PNG")
    with pymupdf.open() as document:
        for _ in pages:
            page = document.new_page()
            page.insert_image(page.rect, stream=content.getvalue())
        document.save(path)
    return path


def use_own_words(monkeypatch, pages):
    import demo.backend.ocr as chain

    monkeypatch.setenv("ENGINE_V2_OCR", "own")
    monkeypatch.setattr(chain, "CHAIN", [LocalOcr()])
    captured = iter(pages)

    def recognize(png, size):
        page, result = next(captured)
        assert png
        assert size == page.pixel_size
        return result.words

    monkeypatch.setitem(coordinate_ocr.ENGINES, "own", recognize)


@pytest.mark.parametrize("boundary", [False, True])
def test_resident_note_false_alarm_is_fixed_in_actual_upload(client, tmp_path, monkeypatch, boundary, scan_guard_off):
    pages = sample.resident(boundary=boundary)
    use_own_words(monkeypatch, pages)
    path = image_pdf(tmp_path / "FAKE-resident-notes.pdf", pages)
    direct = read_document(str(path), DocType.NHIS_PAYMENT)
    assert direct.detected_doc_type == DocType.RESIDENT_ABSTRACT
    assert direct.confidence >= .9
    assert not direct.fields.get("판독검증실패")
    assert not direct.fields.get("판독경고")
    use_own_words(monkeypatch, sample.resident(boundary=boundary))
    response, stored = upload(client, new_app(client, name=sample.NAME, birth=sample.BIRTH), path, "resident_abstract")
    assert response["status"] == "PASS"
    assert response["findings"] == []
    assert stored["fields"] == direct.fields
    assert stored["fields"]["성명"] == sample.NAME
    assert stored["fields"]["생년월일"] == sample.BIRTH


@pytest.mark.parametrize("defect", ["first", "last", "all", "middle", "note", "duplicate", "unreadable"])
def test_resident_remaining_number_uncertainty_reaches_upload_review(client, tmp_path, monkeypatch, defect):
    pages = sample.damage(sample.resident(), defect)
    use_own_words(monkeypatch, pages)
    path = image_pdf(tmp_path / "FAKE-resident-missing-number.pdf", pages)
    response, stored = upload(client, new_app(client, name=sample.NAME, birth=sample.BIRTH), path, "resident_abstract")
    assert response["status"] == "NEEDS_REVIEW"
    assert response["findings"]
    assert all(finding["severity"] != "FAIL" for finding in response["findings"])
    assert stored["confidence"] <= .4
    assert "history_numbers_sequential" in stored["fields"]["판독검증실패"]
    assert stored["fields"]["판독경고"]
    assert stored["fields"]["성명"] == sample.NAME
    assert stored["fields"]["생년월일"] == sample.BIRTH


def _split_first_table_header(pages, index=0):
    """표 머리글의 날짜·세대주 칸이 한 줄 아래로 읽힌 OCR (11-26 회귀 세트). index: 쪽 번호(0부터)."""
    page, result = pages[index]
    for word in result.words:
        if word.text in ("발생일 / 신고일", "세대주및관계"):
            x0, y0, x1, y1 = word.bbox_px
            dy = 0.013 * page.pixel_size[1]
            word.bbox_px = (x0, y0 + dy, x1, y1 + dy)
    return pages


@pytest.mark.parametrize("make,reason", [
    (lambda: _split_first_table_header(sample.resident()), "NUMBER_START"),
    (lambda: sample.resident(offset=3), "NUMBER_START"),
    (lambda: _split_first_table_header(sample.resident(), 2), "UNREAD_ROWS"),
    (lambda: _without_row(sample.resident(), 11), None),
], ids=["first_page_rows_unread", "starts_at_4", "last_page_rows_unread", "last_entry_unread"])
def test_history_not_starting_at_one_is_never_auto_pass(client, tmp_path, monkeypatch, make, reason, scan_guard_off):
    # 11-26: 앞·뒤 이력이 빠진 초본은 남은 순번이 이어져 보여도 자동 적합이 아니다. 스캔 안전장치와 별개로
    # 이 신호만으로 확인필요가 되는지 본다 (안전장치를 끈 상태).
    use_own_words(monkeypatch, make())
    path = image_pdf(tmp_path / "FAKE-resident-leading-rows.pdf", make())
    response, stored = upload(client, new_app(client, name=sample.NAME, birth=sample.BIRTH), path, "resident_abstract")
    assert response["status"] == "NEEDS_REVIEW"
    if reason:
        assert reason in stored["fields"]["주소이력불확실사유"].split(",")
        assert stored["fields"]["주소이력상태"] == "불확실" and stored["fields"]["전입일"] == "불확실"
    else:  # 뒤따르는 건 없는 메모 순번: 엔진 순번 검증 실패 (기존 youth 신뢰도 제한 경로)
        assert "history_numbers_sequential" in stored["fields"]["판독검증실패"]
    assert stored["fields"]["성명"] == sample.NAME


@pytest.mark.parametrize("band", [(37.0, 77.0), (43.8, 77.0)], ids=["bottom_cut", "end_marker_missing"])
def test_unconfirmed_history_end_is_never_auto_pass(client, tmp_path, monkeypatch, band, scan_guard_off):
    # 11-26: 순번이 이어져도 마지막 건 아래 끝 표시가 없으면 끝 이력 누락을 배제할 수 없다 (안전장치를 끈 상태).
    from engine_v2.tests.test_p2_resident import _drop_band

    use_own_words(monkeypatch, _drop_band(sample.resident(), 2, *band))
    path = image_pdf(tmp_path / "FAKE-resident-end.pdf", _drop_band(sample.resident(), 2, *band))
    response, stored = upload(client, new_app(client, name=sample.NAME, birth=sample.BIRTH), path, "resident_abstract")
    assert response["status"] == "NEEDS_REVIEW"
    assert stored["fields"]["주소이력불확실사유"] == "END_UNCONFIRMED"
    assert stored["fields"]["전입일"] == "불확실" and stored["fields"]["현주소시도"] == "불확실"
    assert stored["fields"]["주소이력끝근거"] == "확인되지 않음"


def test_confirmed_history_end_is_recorded(client, tmp_path, monkeypatch, scan_guard_off):
    use_own_words(monkeypatch, sample.resident())
    path = image_pdf(tmp_path / "FAKE-resident-complete.pdf", sample.resident())
    response, stored = upload(client, new_app(client, name=sample.NAME, birth=sample.BIRTH), path, "resident_abstract")
    assert response["status"] == "PASS"
    assert stored["fields"]["주소이력끝근거"] == "이하 여백 (3쪽)"
