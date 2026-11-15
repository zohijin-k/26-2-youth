"""Build the evaluation-only supplement for job_interview_confirmation, and a review capture.

Boxes come from the template's own ruling lines (value cells right of the label column)
and printed text positions ("2026년  월  일"), not from draft.py output. Every box is
"사람 확인 필요" until a person checks the capture. demo/fixtures/form_coords is not touched.

Run: python build_eval_supplement.py [--write]   (prints JSON; --write saves it and the capture)
"""
import json
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'demo/fixtures/templates/job_interview_confirmation.pdf'
OUT = ROOT / 'demo/fixtures/form_draft_eval/job_interview_confirmation.extra.json'
SHOT = Path(__file__).resolve().parent / 'shots/stage3-job_interview_confirmation-supplement.png'
INSET = 2.0


def rules(page):
    horizontal, vertical = [], []
    for drawing in page.get_drawings():
        for item in drawing['items']:
            if item[0] == 'l':
                a, b = item[1], item[2]
                if abs(a.y - b.y) < .5: horizontal.append((round(a.y, 1), min(a.x, b.x), max(a.x, b.x)))
                elif abs(a.x - b.x) < .5: vertical.append((round(a.x, 1), min(a.y, b.y), max(a.y, b.y)))
    return horizontal, vertical


def build():
    with pymupdf.open(TEMPLATE) as document:
        page = document[0]
        horizontal, vertical = rules(page)
        words = page.get_text('words')
        fields = {}
        headings = [w for w in words if w[4] in ('면접기업', '면접현황')]
        band = pymupdf.Rect()
        for drawing in page.get_drawings():
            for item in drawing['items']:
                if item[0] == 're' and any(pymupdf.Rect(item[1]).contains(pymupdf.Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2))
                                           for w in headings):
                    band |= pymupdf.Rect(item[1])
        # Enterprise table: a label cell, then a value cell up to the next rule on the right.
        for name, label in (('company', '회사명'), ('location', '소재지'), ('business', '업태/업종'),
                            ('manager', '담당자'), ('contact', '연락처'), ('datetime', '면접일시'),
                            ('place', '면접장소'), ('job', '응시직군')):
            # Only words inside the enterprise/interview table band; "연락처"/"담당자" repeat elsewhere.
            word = next(w for w in words if w[4] == label and band.y0 <= (w[1] + w[3]) / 2 <= band.y1)
            middle = (word[1] + word[3]) / 2
            top = max(y for y, a, b in horizontal if y < middle and a <= word[0] <= b)
            bottom = min(y for y, a, b in horizontal if y > middle and a <= word[0] <= b)
            crossing = sorted(x for x, a, b in vertical if a <= middle <= b)
            left = min(x for x in crossing if x > word[2])
            right = min(x for x in crossing if x > left + 15)
            fields[f'supplement.{name}'] = {'type': 'text', 'page': 0, 'label': label,
                                            'box': [round(left + INSET, 2), round(top + INSET, 2),
                                                    round(right - INSET, 2), round(bottom - INSET, 2)]}
        fields['supplement.datetime']['note'] = '예시 문구(2026. 00. 00. 00:00~00:00)가 인쇄된 칸'
        # "2026년  월  일": the blanks between the printed tokens.
        line = sorted((w for w in words if w[4] in ('2026년', '월', '일') and w[1] > 540), key=lambda w: w[0])
        for (left, right), part in zip(zip(line, line[1:]), ('month', 'day')):
            fields[f'supplement.written.{part}'] = {'type': 'text', 'page': 0, 'label': '월' if part == 'month' else '일',
                                                   'box': [round(left[2], 2), round(min(left[1], right[1]), 2),
                                                           round(right[0], 2), round(max(left[3], right[3]), 2)]}
        # Signing lines below the table: "회사명 : ___" and "담당자 : ___ (서명/인)".
        below = sorted((w for w in words if w[1] > band.y1 + 100), key=lambda w: (w[1], w[0]))
        seal = next(w for w in below if w[4] == '(서명/인)')
        for name, label in (('sign.company', '회사명'), ('sign.manager', '담당자')):
            word = next(w for w in below if w[4] == label)
            colon = next(w for w in below if w[4] == ':' and abs(w[1] - word[1]) < 2 and w[0] > word[2])
            right = seal[0] if abs(seal[1] - word[1]) < 2 else seal[2]
            fields[f'supplement.{name}'] = {'type': 'text', 'page': 0, 'label': label,
                                            'box': [round(colon[2] + 3, 2), round(word[1], 2), round(right - 3, 2), round(word[3], 2)]}
        fields['supplement.sign.seal'] = {'type': 'image', 'page': 0, 'label': '(서명/인)',
                                          'box': [round(seal[0] - 2, 2), round(seal[1] - 1.5, 2), round(seal[2] + 2, 2), round(seal[3] + 1.5, 2)]}
        supplement = {'form_no': 'job_interview_confirmation', 'purpose': '측정 전용 보충 정답. 렌더링·신청 화면에서 쓰지 않음.',
                      'status': '사람 확인 필요', 'source': '서식 PDF의 괘선과 인쇄 글자 위치에서 계산(build_eval_supplement.py)',
                      'fields': fields}
        if '--write' in sys.argv:
            shape = page.new_shape()
            for field in fields.values():
                shape.draw_rect(pymupdf.Rect(field['box']))
            shape.finish(color=(.85, .1, .1), width=1.2)
            shape.commit()
            for field in fields.values():
                page.insert_text((field['box'][0] + 1, field['box'][1] + 7), field['label'], fontname='korea', fontsize=6,
                                 color=(.85, .1, .1))
            SHOT.parent.mkdir(parents=True, exist_ok=True)
            SHOT.write_bytes(page.get_pixmap(dpi=110, alpha=False).tobytes('png'))
    return supplement


if __name__ == '__main__':
    result = build()
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if '--write' in sys.argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text)
    print(text)
