"""OWN_OCR_INTRA_THREADS / OWN_OCR_PAGE_WORKERS: defaults, overrides, invalid values (synthetic; officer doc_timing recording tests not ported: no tool in youth)."""
import json
import logging
import os
from pathlib import Path
import subprocess
import sys

import pytest

from engine_v2.pipeline.ocr import own

REPO = Path(__file__).resolve().parents[2]
NAMES = ('OWN_OCR_INTRA_THREADS', 'OWN_OCR_PAGE_WORKERS')
PATHLIKE = '/Users/secret-person/x.pdf'


def _import_own(**env):
    """Fresh interpreter: the module-level settings exactly as a new process reads them."""
    clean = {k: v for k, v in os.environ.items() if k not in NAMES}
    done = subprocess.run(
        [sys.executable, '-B', '-c',
         'from engine_v2.pipeline.ocr import own; print(own.INTRA_OP_THREADS, own.MAX_PAGE_WORKERS)'],
        cwd=REPO, env={**clean, **env}, capture_output=True, text=True, timeout=60, check=True)
    return done.stdout.split(), done.stderr.splitlines()


# ---------------------------------------------------------------- parsing


def test_unset_and_empty_keep_the_default_silently(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger=own.__name__)
    monkeypatch.delenv('OWN_OCR_X', raising=False)
    assert own._env_count('OWN_OCR_X', 2) == 2
    for raw in ('', '  '):
        monkeypatch.setenv('OWN_OCR_X', raw)
        assert own._env_count('OWN_OCR_X', 2) == 2
    assert caplog.records == []


@pytest.mark.parametrize('raw, expected', [('1', 1), ('3', 3), (' 8 ', 8), ('16', 16)])
def test_positive_integers_are_used(monkeypatch, caplog, raw, expected):
    caplog.set_level(logging.WARNING, logger=own.__name__)
    monkeypatch.setenv('OWN_OCR_X', raw)
    assert own._env_count('OWN_OCR_X', 2) == expected
    assert caplog.records == []


@pytest.mark.parametrize('raw', ['0', '00', '-1', '-4', 'abc', '2.5', '+3', '3_0', '٣', '1e2', '9999999',
                                 PATHLIKE])
def test_invalid_values_fall_back_with_one_warning_line(monkeypatch, caplog, raw):
    caplog.set_level(logging.WARNING, logger=own.__name__)
    monkeypatch.setenv('OWN_OCR_X', raw)
    assert own._env_count('OWN_OCR_X', 4) == 4
    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert message == 'OWN_OCR_X is not a positive integer; using default 4'
    assert '\n' not in message


# ---------------------------------------------------------------- module settings in a new process


def test_no_environment_gives_2_and_4():
    values, stderr = _import_own()
    assert values == ['2', '4'] and stderr == []


@pytest.mark.parametrize('intra, workers', [('4', '2'), ('1', '4'), ('2', '1'), ('3', '6')])
def test_each_variable_sets_its_value(intra, workers):
    assert _import_own(OWN_OCR_INTRA_THREADS=intra)[0] == [intra, '4']
    assert _import_own(OWN_OCR_PAGE_WORKERS=workers)[0] == ['2', workers]
    values, stderr = _import_own(OWN_OCR_INTRA_THREADS=intra, OWN_OCR_PAGE_WORKERS=workers)
    assert values == [intra, workers] and stderr == []


@pytest.mark.parametrize('bad', ['0', '-2', 'many', PATHLIKE])
def test_invalid_values_give_defaults_and_one_line_each(bad):
    values, stderr = _import_own(OWN_OCR_INTRA_THREADS=bad, OWN_OCR_PAGE_WORKERS=bad)
    assert values == ['2', '4']
    assert stderr == ['OWN_OCR_INTRA_THREADS is not a positive integer; using default 2',
                      'OWN_OCR_PAGE_WORKERS is not a positive integer; using default 4']


# ---------------------------------------------------------------- worker budget


@pytest.mark.parametrize('intra, workers, cap', [(2, 4, 4), (4, 2, 2), (1, 4, 4), (2, 1, 1), (4, 4, 2)])
def test_page_worker_cap_follows_the_settings(monkeypatch, intra, workers, cap):
    monkeypatch.setattr(own.os, 'cpu_count', lambda: 8)
    monkeypatch.setattr(own, 'INTRA_OP_THREADS', intra)
    monkeypatch.setattr(own, 'MAX_PAGE_WORKERS', workers)
    assert own.page_workers(9) == cap and own.page_workers(9) * intra <= 8


def test_one_page_worker_reads_sequentially(monkeypatch):
    from engine_v2.pipeline import ocr
    monkeypatch.setattr(own, 'MAX_PAGE_WORKERS', 1)
    monkeypatch.setattr(own, 'page_sessions', lambda slot: (_ for _ in ()).throw(AssertionError(slot))
                        if slot else None)
    threads = []
    monkeypatch.setitem(ocr.ENGINES, 'own', lambda png, size: threads.append(
        __import__('threading').current_thread().name) or [])
    images = [(b'png', (10, 10))] * 3
    assert own.prepare_page_workers(len(images)) == 1
    for read in ocr.run_ocr_pages('own', images):
        read()
    assert len(threads) == 3 and not any(name.startswith('own-page') for name in threads)
