"""Copy public blank templates under English names and generate a synthetic notice/image in /tmp."""
from pathlib import Path
import shutil
import pymupdf

REPO = Path(__file__).resolve().parents[3]
root = Path('/tmp/form-draft-followup-e2e/files')
root.mkdir(parents=True, exist_ok=True)
for source, target in (('서식2.pdf', 'form2-self-check.pdf'), ('서식5.pdf', 'form5-consent.pdf')):
    shutil.copyfile(REPO / 'demo/fixtures/templates' / source, root / target)
with pymupdf.open() as pdf:
    page = pdf.new_page(width=595, height=842)
    page.insert_text((40, 55), '2026 합성 청년 서식 확인 사업 모집 공고', fontname='korea', fontsize=17)
    for index, text in enumerate(['공고일: 2026.11.15', '신청 기간: 2026.11.15 ~ 2026.12.31',
                                  '지원 대상: 만 18세 이상 39세 이하 청년', '제출 서류: 면접용사진사본',
                                  '신청 방법: 온라인 신청', '문의: 합성청년센터 000-000-0000']):
        page.insert_text((40, 180 + index * 32), text, fontname='korea', fontsize=12)
    page.insert_text((40, 100), 'Synthetic notice. No real personal documents are used.')
    pdf.save(root / 'notice.pdf')
with pymupdf.open() as pdf:
    page = pdf.new_page(width=800, height=900)
    page.draw_rect(pymupdf.Rect(0, 0, 800, 900), color=(.8, .8, .8), fill=(.95, .97, 1))
    page.insert_text((80, 160), 'SYNTHETIC TEST IMAGE', fontsize=34)
    page.draw_circle((400, 500), 150, color=(.2, .4, .6), fill=(.6, .75, .9))
    page.get_pixmap(matrix=pymupdf.Matrix(2, 2)).save(root / 'upload.png')
print('fixtures ready')
