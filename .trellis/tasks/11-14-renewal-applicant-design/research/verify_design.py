"""Static applicant UI audit. Run with the repository virtualenv from any directory."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / 'demo/frontend/src'
tokens = dict(re.findall(r'(--[\w-]+)\s*:\s*([^;}]+)', (SRC / 'styles/tokens.css').read_text()))

def resolve(value):
    while value.startswith('var('):
        value = tokens[value[4:-1]]
    if len(value) == 4:
        value = '#' + ''.join(c * 2 for c in value[1:])
    return value

def luminance(value):
    value = resolve(value)
    channels = [int(value[i:i+2], 16) / 255 for i in (1, 3, 5)]
    rgb = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
    return sum(v * w for v, w in zip(rgb, [.2126, .7152, .0722]))

def ratio(fg, bg):
    a, b = sorted([luminance(tokens[fg]), luminance(tokens[bg])])
    return (b + .05) / (a + .05)

pairs = []
for fg in ['--gray-90', '--gray-70', '--gray-60', '--brand-60', '--brand-50']:
    for bg in ['--gray-0', '--gray-5', '--color-bg', '--brand-5']:
        pairs.append((fg, bg, 4.5))
for color in ['danger', 'warning', 'success', 'info']:
    for bg in ['--gray-0', f'--{color}-5', f'--{color}-10']:
        pairs.append((f'--{color}-60', bg, 4.5))
for bg in ['--brand-60', '--brand-70', '--brand-80']:
    pairs.append(('--gray-0', bg, 7))
pairs += [('--gray-60', '--gray-10', 4.5), ('--success-60', '--brand-tint-a', 4.5), ('--success-60', '--brand-tint-b', 4.5)]
rows = [{'foreground': fg, 'background': bg, 'ratio': round(ratio(fg,bg), 3), 'minimum': minimum} for fg,bg,minimum in pairs]
for row in rows:
    assert row['ratio'] >= row['minimum'], row

files = sorted((SRC/'pages/applicant').glob('*.css')) + [SRC/'styles/base.css', SRC/'styles/components.css', SRC/'forms/pdf-forms-workspace.css']
for path in files:
    css = re.sub(r'/\*.*?\*/', '', path.read_text(), flags=re.S)
    assert not re.search(r'#[\da-f]{3,8}\b|rgba?\(', css, re.I), f'Literal color in {path}'
    for prop, value in re.findall(r'(font-size|border-radius)\s*:\s*([^;}]+)', css):
        assert value.startswith('var(') or value == 'inherit', (path, prop, value)
    widths = re.findall(r'@media[^{}]*max-width:\s*([^)]*)', css)
    assert all(width in ['600px', '900px'] for width in widths), (path, widths)

print(json.dumps({'contrast_pairs': rows, 'files_audited': [str(p.relative_to(ROOT)) for p in files], 'status': 'passed'}, indent=2))
