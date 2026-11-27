"""O2: 4대보험 fallback (both title fragments) applies only when no keyword matches."""
from ..ocr import pdftext
from ..rules.doc_types import DocType


def test_interleaved_and_separated_titles_classify_as_insurance4():
    for text in ('4대 사회보험\n확인용 가입자 가입내역 확인서', '가입자 가입내역 확인서 …… 4대 사회보험'):
        detected, evidence = pdftext.classify_with_evidence(text)
        assert detected is DocType.INSURANCE_4 and '제목 조각' in evidence


def test_existing_keywords_keep_priority_and_fragments_alone_do_not_classify():
    interleaved = '4대 사회보험 확인용 가입자 가입내역 확인서'
    assert pdftext.classify_with_evidence('건강보험료 납부확인서 ' + interleaved)[0] is DocType.NHIS_PAYMENT
    assert pdftext.classify_with_evidence('4대 사회보험 가입자 가입내역 확인서')[1].startswith("본문에서 '4대사회보험")
    assert pdftext.classify_with_evidence('4대 사회보험 안내')[0] is None
    assert pdftext.classify_with_evidence('가입자 가입내역 확인서')[0] is None

