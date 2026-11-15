"""Capture a value-free real-HTTP matrix against the isolated visual server.

Run only after the browser journey is complete; these synthetic mutations change
the isolated database counts. The production app has no visual identity marker.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import httpx

from visual_job import SUITE, _check_visual_server, _ok, route_requests


def main() -> int:
    parser = argparse.ArgumentParser(description='Record isolated synthetic HTTP access checks.')
    parser.add_argument('--base-url', default='http://127.0.0.1:8010')
    args = parser.parse_args()
    rows: list[dict] = []
    result = {'suite': SUITE, 'synthetic_only': True, 'passed': False, 'row_count': 0,
              'rows': rows, 'error_type': None}
    # No existing browser or user cookie jar is imported or modified.
    try:
        with (httpx.Client(timeout=30, trust_env=False) as owner,
              httpx.Client(timeout=30, trust_env=False) as other,
              httpx.Client(timeout=30, trust_env=False) as officer):
            _check_visual_server(owner, args.base_url)
            # Only the fixed test credential of the isolated visual wrapper.
            _ok(officer.post(args.base_url.rstrip('/') + '/api/officer/login',
                            json={'password': 'synthetic-visual-password'}))
            route_requests(args.base_url, owner, other, officer, rows_out=rows)
        for row in rows:
            expected = 200 if row['expected'] == 'public' else 401 if row['expected'] == 'officer' else 403
            assert row['anonymous'] == expected and row['other'] == expected, 'Unexpected access boundary'
            assert row['owner_or_officer'] == 200, 'Valid synthetic actor was rejected'
        assert len(rows) >= 42, 'The complete route matrix is required'
        result['passed'] = True
    except Exception as error:
        # Retain completed request rows even on failure. Do not copy response
        # bodies, headers, cookie values, credentials or exception messages.
        result['error_type'] = type(error).__name__
    result['row_count'] = len(rows)
    output = Path(__file__).resolve().parent / 'security-matrix.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'passed': result['passed'], 'row_count': len(rows), 'error_type': result['error_type']}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
