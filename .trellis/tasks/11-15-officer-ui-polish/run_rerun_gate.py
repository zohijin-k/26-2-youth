"""Stage3 rerun gate. Allocate/clean only owned temp directories; stop on ENOSPC."""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / 'rerun'
PYTHON = ROOT / '.venv/bin/python'
MODE = sys.argv[1]
assert MODE in {'code', 'docs'}
results = {'engine': None, 'backend': None, 'scenarios': {}, 'frontend': None, 'disk': []}
class StopGate(Exception):
    pass

def persist():
    (OUT / f'gate-{MODE}.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')

def disk(label):
    free = shutil.disk_usage(ROOT).free
    results['disk'].append({'suite': label, 'free_bytes': free})
    with (OUT / f'disk-{MODE}.txt').open('a') as output:
        output.write(label + '\n' + subprocess.check_output(['df', '-h', '/'], text=True))
    return free

def run(label, command, cwd=ROOT):
    disk(label + '-before')
    scratch = None
    if label in {'engine', 'backend'}:
        scratch = Path(tempfile.mkdtemp(prefix=f'officer-stage3-rerun-{MODE}-{label}-', dir='/tmp'))
        command = [*command, '--basetemp', str(scratch)]
    log = Path('/tmp') / f'officer-stage3-rerun-{MODE}-{label}.log'
    enospc = False
    process = None
    try:
        with log.open('w') as output:
            environment = {**os.environ, 'LLM_PROVIDER': 'none', 'PROGRAM_LLM_ENABLED': 'false'}
            process = subprocess.Popen(command, cwd=cwd, stdout=output, stderr=subprocess.STDOUT, env=environment)
            while process.poll() is None:
                time.sleep(1)
                tail = log.read_text(errors='replace')[-65536:]
                if re.search(r'ENOSPC|No space left on device|\[Errno 28\]', tail, re.I):
                    enospc = True
                    process.terminate()
                    try: process.wait(timeout=10)
                    except subprocess.TimeoutExpired: process.kill(); process.wait()
                    break
        output_text = log.read_text(errors='replace')
        enospc = enospc or bool(re.search(r'ENOSPC|No space left on device|\[Errno 28\]', output_text, re.I))
        code = process.returncode or 0
    except OSError as error:
        if error.errno != 28: raise
        enospc = True
        code = 99
        output_text = 'ENOSPC while writing this run temporary output'
    finally:
        if process and process.poll() is None:
            process.terminate(); process.wait(timeout=10)
        if scratch and scratch.exists():
            shutil.rmtree(scratch)
    summary = re.findall(r'^.*(?:\d+ passed|\d+ failed|통과.*실패|tests |pass |fail |warnings?|built in).*$' , output_text, re.M)[-8:]
    minimum = {'engine': 1267, 'backend': 1645}.get(label, 0)
    counts = re.findall(r'(\d+) passed', output_text)
    if minimum and (not counts or int(counts[-1]) < minimum): code = code or 1
    if label == 'frontend' and re.search(r'(?mi)(^.*warning|chunks are larger)', output_text): code = code or 1
    row = {'exit': 99 if enospc else code, 'summary': summary, 'log': str(log), 'enospc': enospc}
    if label.startswith('run_p'): results['scenarios'][label] = row
    else: results[label] = row
    disk(label + '-after')
    persist()
    print(label + ': ' + ('PASS' if row['exit'] == 0 else 'FAIL'), flush=True)
    if row['exit']:
        raise StopGate('ENOSPC: cleaned only allocated suite directory; stop' if enospc else 'Suite failed; stop')

try:
    if disk('gate-start') < 15_000_000_000:
        raise StopGate('Less than15GB free before gate; stop')
    run('engine', [str(PYTHON), '-m', 'pytest', 'engine_v2/tests', '-q'])
    run('backend', [str(PYTHON), '-m', 'pytest', 'demo/backend/tests', '-q'])
    modules = sorted(ROOT.glob('demo/backend/tests/run_p*_scenarios.py'))
    assert len(modules) == 18, 'Expected18 unchanged scenario modules'
    for module in modules:
        run(module.stem, [str(PYTHON), '-m', 'demo.backend.tests.' + module.stem])
    run('frontend', ['zsh', '-c', 'npx tsc -b && npx oxlint && npx vite build && node --test src/forms/phone.test.ts src/pages/officer/bulk-actions.test.ts src/lib/*.test.ts tests/*.test.ts'], ROOT / 'demo/frontend')
    results['result'] = 'passed'
except StopGate as error:
    results['result'] = 'failed'
    results['reason'] = str(error)
finally:
    persist()
print(results['result'], flush=True)
raise SystemExit(0 if results['result'] == 'passed' else 1)
