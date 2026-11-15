"""Per-page draft timing over the repository's public blank templates (max of 5 runs)."""
from pathlib import Path
import json
import time

import pymupdf

from demo.backend.forms.draft import _vector_fields

ROOT = Path(__file__).resolve().parents[3]
rows = []
for path in sorted((ROOT / 'demo/fixtures/templates').glob('*.pdf')):
    with pymupdf.open(path) as document:
        for page in document:
            runs = []
            for _ in range(5):
                started = time.perf_counter()
                count = len(_vector_fields(page, page.number))
                runs.append(time.perf_counter() - started)
            rows.append({'template': path.name, 'page': page.number + 1, 'drawings': len(page.get_drawings()),
                         'fields': count, 'max_seconds': round(max(runs), 3)})
(Path(__file__).parent / 'page-timing.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
for row in rows:
    print(f"{row['template']} p{row['page']} drawings={row['drawings']} fields={row['fields']} max={row['max_seconds']}s")
