"""PP-OCRv5 DB detection + Korean CTC recognition, exclusively ONNX CPU.

Algorithms implemented here; model and upstream attribution in docs/own-ocr.md.
No automatic download and no filename-based recognition.
"""
from __future__ import annotations

from functools import lru_cache
import logging
import math
import os
import re
import threading

from ...tools.fetch_own_models import MODEL_DIR, verify_models
from . import OcrWord
from ..privacy import mask_words


def ctc_decode(probabilities, characters: list[str]) -> tuple[str, float]:
    """Blank=0, collapse adjacent repeats BEFORE removing blank; mean emitted score."""
    import numpy as np
    probs = np.asarray(probabilities)
    if probs.ndim != 2 or probs.shape[1] != len(characters) + 1:
        raise ValueError('CTC class count does not match pinned dictionary')
    if not len(probs):
        return '', 0.0
    ids = probs.argmax(axis=1)
    keep = (ids != 0) & np.r_[True, ids[1:] != ids[:-1]]
    text = ''.join(characters[int(i) - 1] for i in ids[keep])
    return text, float(probs[np.arange(len(ids))[keep], ids[keep]].mean()) if keep.any() else 0.0


def polygon_bbox(points, source_size, map_size):
    """Map polygon coordinates to top-left pixel bounds of original input."""
    import numpy as np
    pts = np.asarray(points, dtype=float) * (np.asarray(source_size) / np.asarray(map_size))
    pts = np.clip(pts, (0, 0), source_size)
    return tuple(float(v) for v in (*pts.min(axis=0), *pts.max(axis=0)))


_log = logging.getLogger(__name__)


def _env_count(name: str, default: int) -> int:
    """Positive integer from environment variable ``name``; unset or empty → default.

    Anything else (0, negative, not 1-6 plain decimal digits) gives the default, with one
    warning line that names the variable but never echoes its value.
    """
    raw = os.environ.get(name, '').strip()
    if not raw:
        return default
    if re.fullmatch('[0-9]{1,6}', raw) and int(raw) > 0:
        return int(raw)
    _log.warning('%s is not a positive integer; using default %d', name, default)
    return default


#: onnxruntime threads per session (env OWN_OCR_INTRA_THREADS, read at import).
#: Page workers are bounded so that workers x INTRA_OP_THREADS never exceeds the
#: logical CPU count.
INTRA_OP_THREADS = _env_count('OWN_OCR_INTRA_THREADS', 2)
#: Upper bound on concurrent page sessions (memory: one det+rec pair each);
#: env OWN_OCR_PAGE_WORKERS, read at import. 1 reads pages sequentially.
MAX_PAGE_WORKERS = _env_count('OWN_OCR_PAGE_WORKERS', 4)
_worker = threading.local()


def _load_sessions():
    verify_models(MODEL_DIR)
    import onnxruntime as ort
    ort.disable_telemetry_events()
    options = ort.SessionOptions()
    options.intra_op_num_threads = INTRA_OP_THREADS
    options.inter_op_num_threads = 1
    det, rec = [ort.InferenceSession(str(MODEL_DIR / name), sess_options=options,
                                    providers=['CPUExecutionProvider']) for name in ('det.onnx', 'rec.onnx')]
    chars = (MODEL_DIR / 'korean_dict.txt').read_text(encoding='utf-8').splitlines() + [' ']
    embedded = rec.get_modelmeta().custom_metadata_map.get('character')
    if embedded is not None and embedded.splitlines() != chars[:-1]:
        raise ValueError('own model metadata does not match pinned Korean dictionary')
    if rec.get_outputs()[0].shape[-1] != len(chars) + 1:
        raise ValueError('own recognition class count does not match dictionary')
    return det, rec, chars


@lru_cache(maxsize=1)
def sessions():
    return _load_sessions()


@lru_cache(maxsize=None)
def page_sessions(slot: int):
    """Sessions owned by one concurrent page worker; slot 0 is the shared sessions()."""
    return sessions() if slot == 0 else _load_sessions()


def page_workers(pages: int) -> int:
    """Concurrent page readers for a document, within the CPU budget."""
    return max(1, min(pages, MAX_PAGE_WORKERS, (os.cpu_count() or 1) // INTRA_OP_THREADS))


def prepare_page_workers(pages: int) -> int:
    """Load every worker slot in the calling thread; 1 (sequential) when any load fails."""
    workers = page_workers(pages)
    try:
        for slot in range(workers):
            page_sessions(slot)
    except Exception:  # noqa: BLE001 - the sequential path reports the same error per page
        return 1
    return workers


def bind_page_worker(slot: int) -> None:
    """Thread initializer: recognize() in this thread uses page_sessions(slot)."""
    _worker.slot = slot


def _ordered_box(points):
    import numpy as np
    # Sort left/right pairs, then top/bottom, avoiding duplicate corners on diamonds.
    p = points[np.argsort(points[:, 0])]
    left, right = p[:2][np.argsort(p[:2, 1])], p[2:][np.argsort(p[2:, 1])]
    return np.array([left[0], right[0], right[1], left[1]], dtype=np.float32)


def _detect(image, session):
    import cv2
    import numpy as np
    import pyclipper
    h, w = image.shape[:2]
    ratio = min(1.0, 1600 / max(h, w))
    rh, rw = [max(32, round(v * ratio / 32) * 32) for v in (h, w)]
    resized = cv2.resize(image, (rw, rh)).astype(np.float32) / 255
    tensor = ((resized - np.array([.485, .456, .406], dtype=np.float32)) /
              np.array([.229, .224, .225], dtype=np.float32)).transpose(2, 0, 1)[None]
    pred = session.run(None, {session.get_inputs()[0].name: tensor})[0][0, 0]
    mask = (pred > .3).astype(np.uint8)
    contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    mh, mw = pred.shape
    boxes = []
    for contour in contours[:2000]:
        rect = cv2.minAreaRect(contour)
        if min(rect[1]) < 3:
            continue
        region = np.zeros_like(mask)
        cv2.fillPoly(region, [contour], 1)
        if cv2.mean(pred, region)[0] < .5:
            continue
        poly = cv2.boxPoints(rect)
        perimeter = cv2.arcLength(poly, True)
        if perimeter <= 0:
            continue
        offset = pyclipper.PyclipperOffset()
        offset.AddPath((poly * 1024).astype(np.int64).tolist(), pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
        expanded = offset.Execute(cv2.contourArea(poly) * 1.5 / perimeter * 1024)
        if len(expanded) != 1:
            continue
        box = _ordered_box(cv2.boxPoints(cv2.minAreaRect(np.array(expanded[0], dtype=np.float32) / 1024)))
        box *= np.array([w / mw, h / mh], dtype=np.float32)
        box = np.clip(box, (0, 0), (w - 1, h - 1)).astype(np.float32)
        boxes.append(box)
    return _align_glyph_boxes(boxes, (w, h))


#: (11-26) A box whose long side is under this multiple of its short side holds one or two glyphs.
#: Its minAreaRect angle then follows the glyph shape (the diagonal stroke of "7", a lone ")"),
#: not a text line, and warping along it rotates the glyph (synthetic scan: "7" at +26 deg read "1").
GLYPH_BOX_MAX_ASPECT = 1.5
#: Boxes at least this elongated are text lines; their median angle is the page text angle.
LINE_BOX_MIN_ASPECT = 2.0
#: Glyph boxes within this many degrees of the page text angle keep their detected corners.
GLYPH_ANGLE_TOLERANCE = 3.0


def _box_angle(box) -> float:
    """Top-edge angle in degrees, folded to [-45, 45) (a rectangle repeats every 90 degrees)."""
    dx, dy = (float(v) for v in box[1] - box[0])
    return (math.degrees(math.atan2(dy, dx)) + 45) % 90 - 45


def _box_aspect(box) -> float:
    import numpy as np
    width, height = float(np.linalg.norm(box[1] - box[0])), float(np.linalg.norm(box[3] - box[0]))
    return max(width, height) / max(min(width, height), 1e-6)


def _align_glyph_boxes(boxes, size):
    """Re-frame glyph-sized boxes along the page text angle; every other box is returned as is.

    The page text angle is the median angle of elongated (line) boxes. Without line boxes nothing
    changes. A re-framed box is the rectangle at the page angle that encloses the detected box, so
    no detected ink is cut off; its corners stay in the [tl, tr, br, bl] order _crop expects.
    """
    import numpy as np
    lines = [_box_angle(box) for box in boxes if _box_aspect(box) >= LINE_BOX_MIN_ASPECT]
    if not lines:
        return boxes
    page_angle = float(np.median(lines))
    theta = math.radians(page_angle)
    rotation = np.array([[math.cos(theta), -math.sin(theta)],
                         [math.sin(theta), math.cos(theta)]], dtype=np.float32)
    w, h = size
    aligned = []
    for box in boxes:
        off = (_box_angle(box) - page_angle + 45) % 90 - 45
        if _box_aspect(box) < GLYPH_BOX_MAX_ASPECT and abs(off) > GLYPH_ANGLE_TOLERANCE:
            local = box @ rotation  # rotate by -page_angle: page text axis -> image axis
            (x0, y0), (x1, y1) = local.min(axis=0), local.max(axis=0)
            rect = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float32) @ rotation.T
            box = np.clip(rect, (0, 0), (w - 1, h - 1)).astype(np.float32)
        aligned.append(box)
    return aligned


def _crop(image, box):
    import cv2
    import numpy as np
    width = max(1, round(max(np.linalg.norm(box[0] - box[1]), np.linalg.norm(box[2] - box[3]))))
    height = max(1, round(max(np.linalg.norm(box[0] - box[3]), np.linalg.norm(box[1] - box[2]))))
    dst = np.array([[0, 0], [width-1, 0], [width-1, height-1], [0, height-1]], dtype=np.float32)
    crop = cv2.warpPerspective(image, cv2.getPerspectiveTransform(box, dst), (width, height), borderMode=cv2.BORDER_REPLICATE)
    return np.rot90(crop) if height / width >= 1.5 else crop


def recognize(png: bytes, size: tuple[int, int]) -> list[OcrWord]:
    slot = getattr(_worker, 'slot', 0)
    # Clear missing-model error even without optional image libraries.
    det, rec, chars = sessions() if slot == 0 else page_sessions(slot)
    import cv2
    import numpy as np
    image = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.shape[1::-1] != tuple(size):
        raise ValueError('own input size must match decoded image pixel size')
    words = []
    for box in _detect(image, det):
        crop = _crop(image, box)
        h, w = crop.shape[:2]
        width = max(320, math.ceil(48 * w / h))
        if width > 4096:
            raise ValueError('own text line exceeds supported width (4096)')
        content_w = min(width, math.ceil(48 * w / h))
        tensor = np.zeros((1, 3, 48, width), dtype=np.float32)
        normalized = cv2.resize(crop, (content_w, 48)).astype(np.float32) / 127.5 - 1
        tensor[0, :, :, :content_w] = normalized.transpose(2, 0, 1)
        pred = rec.run(None, {rec.get_inputs()[0].name: tensor})[0][0]
        text, confidence = ctc_decode(pred, chars)
        if text.strip():
            words.append(OcrWord(text, confidence, polygon_bbox(box, size, size)))
    return mask_words(sorted(words, key=lambda word: (round(word.bbox_px[1] / 15), word.bbox_px[0])))
