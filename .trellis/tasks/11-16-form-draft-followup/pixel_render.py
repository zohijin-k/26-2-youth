"""Render existing coordinate forms with fixed synthetic choices; compare PNG pixels across code versions.

Usage: python pixel_render.py <out-dir>   (writes one PNG per case and a sha256 index)
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from demo.backend.forms.coords import load  # noqa: E402
from demo.backend.forms.render import render, render_page_png  # noqa: E402
from demo.backend.forms.values import FilledForm  # noqa: E402

CASES = {
    'form2_radio_text': ('서식2', ['self_check.1.예', 'self_check.2.아니오', 'self_check.3.예', 'self_check.5.아니오']),
    'form1_box_checks': ('서식1', ['savingPurpose.주거자금', 'priorJoined.미참여']),
    'consent_box_checks': ('job_consent', ['consent.privacy.동의함', 'consent.thirdParty.동의하지 않음']),
    'application_box_checks': ('job_application', ['subsidy.interview.면접비', 'subsidy.photo.면접사진촬영비']),
}
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
index = {}
for name, (form_no, checks) in CASES.items():
    coords = load(form_no)
    pdf = render(coords, FilledForm(form_no=form_no, checks=list(checks)))
    png = render_page_png(pdf, 1, 110)
    (out / f'{name}.png').write_bytes(png)
    index[name] = hashlib.sha256(png).hexdigest()
(out / 'index.json').write_text(json.dumps(index, indent=2) + '\n')
print(json.dumps(index, indent=2))
