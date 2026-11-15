"""Commit explicitly named stage paths after the user's mandatory staged checks."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

root = Path(__file__).resolve().parents[3]
gate = json.loads((Path(__file__).parent / ('gate-' + sys.argv[1].split('::', 1)[0] + '.json')).read_text())
assert all(row['exit'] == 0 for row in gate['scenarios'].values()), 'Scenario gate failed'
assert all(gate[name]['exit'] == 0 for name in ('engine', 'backend', 'frontend')), 'Suite gate failed'
assert len(gate['scenarios']) >= 18, 'Missing scenario modules'
for name, minimum in [('engine', 1267), ('backend', 1317)]:
    counts = re.findall(r'(\d+) passed', '\n'.join(gate[name]['summary']))
    assert counts and max(map(int, counts)) >= minimum, f'{name} below baseline'
frontend_log = Path(gate['frontend']['log']).read_text()
assert not re.search(r'(?mi)^.*warning|chunks are larger', frontend_log), 'Frontend warnings remain'
sys.argv[1] = sys.argv[1].split('::', 1)[1]
if sys.argv[2:]:
    subprocess.run(['git','add','--',*sys.argv[2:]], cwd=root, check=True)
diff = subprocess.check_output(['git','diff','--cached'], cwd=root)
names = subprocess.check_output(['git','diff','--cached','--name-only'], cwd=root).decode().splitlines()
protected = json.loads((Path(__file__).parent/'protected-files.json').read_text())
assert not re.search(rb'sk-[A-Za-z0-9-]{10,}', diff), 'Potential API key in staged diff'
assert ('data'+'/private').encode() not in diff, 'Excluded storage reference in staged diff'
for name in names:
    assert name not in protected, f'Protected detail file: {name}'
    assert name not in ['logo.png','.trellis/tasks/11-14-renewal-applicant-design/task.json'], f'Pre-existing user file: {name}'
for name, digest in protected.items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest() == digest, f'Protected detail changed: {name}'
subprocess.run(['git','diff','--cached','--check'], cwd=root, check=True)
subprocess.run(['git','commit','-m',sys.argv[1]], cwd=root, check=True)
subprocess.run(['git','log','-1','--oneline'], cwd=root, check=True)
