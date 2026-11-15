"""Fail closed before each authorized stage commit; never print secret values."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[3]
def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

paths = git('diff', '--cached', '--name-only', '-z').decode().split('\0')
protected = json.loads((Path(__file__).parent / 'protected-files.json').read_text())
for name, digest in protected.items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, 'Protected file changed'
for path in paths:
    assert path not in protected, 'Protected file staged'
    assert path not in {'logo.png', '.trellis/tasks/11-14-renewal-applicant-design/task.json'}, 'User file staged'
    assert not path or Path(path).name != '.' + 'env', 'Secret configuration staged'
diff = git('diff', '--cached')
assert not re.search(rb'sk-[A-Za-z0-9-]{10,}', diff), 'Secret-shaped value staged'
assert b'data/' + b'private' not in diff, 'Forbidden source reference staged'
key = dotenv_values(ROOT / ('.' + 'env')).get('JBAI_API_KEY')
assert not key or key.encode() not in diff, 'Secret value staged'
assert git('diff', '--cached', '--check') == b'', 'Whitespace errors staged'
print('Staged secret, path, protected-file and whitespace checks passed')
