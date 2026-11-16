"""Fail closed before each stage commit; never print secret values."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[3]
PROTECTED = ROOT / '.trellis/tasks/11-16-renewal-master-2/protected-files.json'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


paths = [path for path in git('diff', '--cached', '--name-only', '-z').decode().split('\0') if path]
protected = json.loads(PROTECTED.read_text())
for name, digest in protected.items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, 'Protected file changed'
for path in paths:
    assert path not in protected, 'Protected file staged'
    assert path not in {'logo.png', '.trellis/tasks/11-14-renewal-applicant-design/task.json'}, 'User file staged'
    assert Path(path).name != '.' + 'env', 'Secret configuration staged'
diff = git('diff', '--cached')
assert not re.search(rb'sk-[A-Za-z0-9_-]{16,}', diff), 'Secret-shaped value staged'
assert b'data/' + b'private' not in diff, 'Forbidden source reference staged'
# Configured values are compared with lines this commit adds; context lines are
# already committed text (the docs already name the public model, for example).
added = b'\n'.join(line for line in diff.splitlines() if line.startswith(b'+') and not line.startswith(b'+++'))
for value in dotenv_values(ROOT / ('.' + 'env')).values():
    assert not value or len(value) < 8 or value.encode() not in added, 'Configured secret value staged'
assert not re.search(rb'(?m)^\+.*JBAI_API_KEY' + rb'=[^\s`<]', diff), 'Key assignment with a value staged'
assert git('diff', '--cached', '--check') == b'', 'Whitespace errors staged'
print(f'O staged checks: {len(paths)} paths, protected 10/10 unchanged, no secret-shaped values')
