"""One real end-to-end run with the default format and its single fallback.

Prints only per-call mode, HTTP status and seconds plus the accepted count.
Never prints keys, hosts, model names or bodies. At most 2 real calls.
"""
from pathlib import Path
import json
import socket
import sys
import time
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from demo.backend.llm_drafts import _http_transport  # noqa: E402
from demo.backend.notice_analysis import analyze_notice  # noqa: E402
from demo.backend.notice_llm import configured_notice_provider, enrich_notice  # noqa: E402
from demo.backend.tools.probe_jbai_notice import NOTICES, _env, public_pdf, screen_violations, notice_payload  # noqa: E402

calls = []


def transport(url, headers, body, timeout):
    if len(calls) >= 2:
        raise RuntimeError('budget')
    kind = body.get('response_format', {}).get('type', 'prompt')
    started = time.perf_counter()
    status = 'error'
    try:
        result = _http_transport(url, headers, body, timeout)
        status = 200
        return result
    except HTTPError as error:
        status = error.code
        raise
    except (TimeoutError, socket.timeout):
        status = 'timeout'
        raise
    except URLError as error:
        status = 'timeout' if isinstance(error.reason, (TimeoutError, socket.timeout)) else 'network'
        raise
    finally:
        calls.append({'mode': kind, 'status': status, 'seconds': round(time.perf_counter() - started, 2)})


environ = _env(ROOT / '.env')
environ.pop('JBAI_RESPONSE_FORMAT', None)  # measure the repository default (json_schema)
provider = configured_notice_provider(environ=environ, transport=transport)
assert provider.name == 'jbai'
pages, supplemental = NOTICES['A']
draft = analyze_notice(public_pdf(pages), supplemental)
started = time.perf_counter()
result = enrich_notice(draft, supplemental, provider=provider)
total = round(time.perf_counter() - started, 2)
print(json.dumps({'calls': calls, 'total_seconds': total, 'accepted': len(result.get('suggestions', [])),
                  'screen_violation': screen_violations(draft, notice_payload(draft, supplemental), result)},
                 ensure_ascii=False))
