"""Check a submitted (written) PDF from the E2E run for circle marks and save a page capture.

Run: python e2e_submitted.py <mode>   (reads /tmp/form-draft-followup-e2e/submitted-<mode>.pdf)
Counts stroked, unfilled curve paths (the ○ marks) and filled squares (□ check marks) per page.
"""
import json
import sys
from pathlib import Path

import pymupdf

MODE = sys.argv[1]
assert MODE in {'committed', 'stage1-patch', 'decision'}
HERE = Path(__file__).resolve().parent
source = Path(f'/tmp/form-draft-followup-e2e/submitted-{MODE}.pdf')
report = {'mode': MODE, 'pages': []}
with pymupdf.open(source) as pdf:
    for page in pdf:
        drawings = page.get_drawings()
        ovals = [[round(v, 1) for v in path['rect']] for path in drawings
                 if path.get('fill') is None and any(item[0] == 'c' for item in path['items'])]
        filled = sum(1 for path in drawings if path.get('fill') is not None and path['rect'].width < 20)
        report['pages'].append({'page': page.number, 'circle_marks': len(ovals), 'circle_boxes': ovals[:20],
                                'filled_small_marks': filled})
    (HERE / 'shots' / f'{MODE}-08-submitted-form2.png').write_bytes(pdf[0].get_pixmap(dpi=110, alpha=False).tobytes('png'))
(HERE / f'e2e-submitted-{MODE}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'mode': MODE, 'circle_marks': [p['circle_marks'] for p in report['pages']],
                  'filled_small_marks': [p['filled_small_marks'] for p in report['pages']]}))
