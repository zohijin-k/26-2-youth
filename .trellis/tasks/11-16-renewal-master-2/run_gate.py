"""Run the unchanged acceptance suites, keeping logs outside the repository."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
PYTHON = ROOT / '.venv/bin/python'

def run(label, command, cwd=ROOT):
    log = Path('/tmp') / f'renewal-{sys.argv[1]}-{label}.log'
    with log.open('w') as output:
        environment = {**os.environ, 'LLM_PROVIDER': 'none', 'PROGRAM_LLM_ENABLED': 'false'}
        result = subprocess.run(command, cwd=cwd, stdout=output, stderr=subprocess.STDOUT, env=environment)
    text = log.read_text(errors='replace')
    summary = re.findall(r'^.*(?:\d+ passed|\d+ failed|tests |pass |fail |warnings?|built in).*$' , text, re.M)[-8:]
    failed = result.returncode
    counts = re.findall(r'(\d+) passed', text)
    minimum = {'engine': 1267, 'backend': 1412}.get(label, 0)
    if minimum and (not counts or int(counts[-1]) < minimum): failed = failed or 1
    if label == 'frontend' and re.search(r'(?mi)(^.*warning|chunks are larger)', text): failed = failed or 1
    return {'exit': failed, 'summary': summary, 'log': str(log)}

def scenarios():
    rows = {}
    for path in sorted(ROOT.glob('demo/backend/tests/run_p*_scenarios.py')):
        rows[path.stem] = run(path.stem, [str(PYTHON), '-m', f'demo.backend.tests.{path.stem}'])
    return rows

commands = {
    'engine': lambda: run('engine', [str(PYTHON), '-m', 'pytest', 'engine_v2/tests', '-q']),
    'backend': lambda: run('backend', [str(PYTHON), '-m', 'pytest', 'demo/backend/tests', '-q']),
    'scenarios': scenarios,
    'frontend': lambda: run('frontend', ['zsh', '-c', 'npx tsc -b && npx oxlint && npx vite build && node --test src/forms/phone.test.ts src/pages/officer/bulk-actions.test.ts src/lib/*.test.ts tests/*.test.ts'], ROOT / 'demo/frontend'),
}
# OCR benchmark subprocesses can be killed under concurrent model memory pressure.
results = {'engine': commands.pop('engine')()}
# Keep wall-clock comparison scenarios free from concurrent suite load.
for name, command in commands.items():
    results[name] = command()
output = ROOT / '.trellis/tasks/11-16-renewal-master-2' / f'gate-{sys.argv[1]}.json'
output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(results, ensure_ascii=False, indent=2), flush=True)
failed = any(value['exit'] for name, value in results.items() if name != 'scenarios') or any(row['exit'] for row in results['scenarios'].values())
raise SystemExit(1 if failed else 0)
