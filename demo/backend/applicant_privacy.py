"""Mask resident-number text before applicant-authored JSON is persisted."""
from __future__ import annotations

import base64
from typing import Any

from engine_v2.pipeline.privacy import mask_data

_SIGNATURE_KEYS = frozenset({'signature', 'job.signature', 'consent.job.signature'})


def _png_signature(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith('data:image/png;base64,'):
        return False
    try:
        raw = base64.b64decode(value.split(',', 1)[1], validate=True)
        if not raw.startswith(b'\x89PNG\r\n\x1a\n') or len(raw) > 5 * 1024 * 1024:
            return False
        import pymupdf
        with pymupdf.open(stream=raw, filetype='png') as image:
            return image.page_count == 1
    except Exception:
        return False


def mask_form_values(value: Any) -> Any:
    """Apply the shared recognizer to text/keys, preserving valid PNG signatures.

    Image data is not text: changing base64 digits would corrupt a signature.
    Only the established signature fields can take this binary-data exception.
    """
    if isinstance(value, dict):
        return {mask_data(key): item if key in _SIGNATURE_KEYS and _png_signature(item) else mask_form_values(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [mask_form_values(item) for item in value]
    if isinstance(value, tuple):
        return tuple(mask_form_values(item) for item in value)
    return mask_data(value)
