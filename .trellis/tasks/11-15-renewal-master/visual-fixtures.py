"""Generate only fictitious visual-test files under /tmp."""
from pathlib import Path
import json
import sys
import pymupdf
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from demo.backend.forms.draft import draft_layout

root = Path('/tmp/renewal-visual-fixtures')
root.mkdir(parents=True, exist_ok=True)
with pymupdf.open() as pdf:
    page = pdf.new_page(width=595, height=842)
    page.insert_text((40, 55), 'SYNTHETIC PROGRAM NOTICE - TEST ONLY', fontsize=17)
    page.insert_text((40, 100), 'Apply with identity verification, a completed form and one image.')
    page.insert_text((40, 125), 'No real personal documents or real applicants are used.')
    pdf.save(root / 'visual-notice.pdf')
with pymupdf.open() as pdf:
    page = pdf.new_page(width=595, height=842)
    page.insert_text((40, 55), 'SYNTHETIC PROGRAM APPLICATION', fontsize=17)
    page.insert_text((40, 80), 'TEST ONLY - no real personal data', fontsize=10)
    page.draw_rect(pymupdf.Rect(40, 110, 545, 320))
    page.draw_line((190, 110), (190, 320))
    for y in (180, 250): page.draw_line((40, y), (545, y))
    for label, y in (('Name', 150), ('Message', 220), ('Signature', 290)):
        page.insert_text((60, y), label, fontsize=13)
    pdf.save(root / 'visual-form.pdf')
    layout = draft_layout(pdf.tobytes())
    assert len(layout['fields']) == 3, layout
    assert {field['field_type'] for field in layout['fields'].values()} == {'text', 'signature'}
with pymupdf.open() as pdf:
    page = pdf.new_page(width=800, height=900)
    page.draw_rect(pymupdf.Rect(0, 0, 800, 900), color=(.8, .8, .8), fill=(.95, .97, 1))
    page.insert_text((80, 160), 'SYNTHETIC TEST IMAGE', fontsize=34)
    page.insert_text((80, 220), 'No document type and no personal data.', fontsize=19)
    page.draw_circle((400, 500), 150, color=(.2, .4, .6), fill=(.6, .75, .9))
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
    assert pixmap.width >= 1400 and pixmap.height >= 1400
    pixmap.save(root / 'visual-upload.png')
(root / 'manifest.json').write_text(json.dumps({'notice': str(root / 'visual-notice.pdf'),
    'form': str(root / 'visual-form.pdf'), 'image': str(root / 'visual-upload.png'),
    'draft_fields': 3, 'image_size': [1600, 1800]}, indent=2) + '\n')
print(root / 'manifest.json')
