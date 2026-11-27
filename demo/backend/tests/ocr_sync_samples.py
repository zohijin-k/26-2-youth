"""Synthetic samples for the common-OCR tests ported from savings-officer (11-27 sync).

Copied verbatim from officer engine_v2/tests/test_classify_recovery_diag.py (render-retry PDFs) and
test_classify_recovery_diag_s1.py (2-up sheets); youth has no classify_recovery_diag tool. Synthetic only.
"""
import io

import pymupdf  # noqa: F401 - used inside builders
from PIL import Image  # noqa: F401

from engine_v2.pipeline.ocr import OcrResult
from engine_v2.pipeline.preprocess import PageImage, PageSource
from engine_v2.tests.test_resident_abstract import H, W, header, row, table_head


PAYMENT_TITLE = ('건강보험료', '납부확인서')


def _picture(width=600, height=848):
    from PIL import Image, ImageDraw
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    for row in range(8):
        draw.rectangle((40, 60 + row * 90, 40 + 60 * (row % 5 + 3), 80 + row * 90), fill='black')
    return image


def _png(image):
    data = io.BytesIO()
    image.save(data, 'PNG')
    return data.getvalue()


def _image_page(document, image=None):
    page = document.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=_png(image or _picture()))
    return page


def _raw_page(document, xrefs):
    page = document.new_page(width=595, height=842)
    names = ' '.join(f'/Im{i} {x} 0 R' for i, x in enumerate(xrefs))
    document.xref_set_key(page.xref, 'Resources', f'<< /XObject << {names} >> >>')
    content = document.get_new_xref()
    document.update_object(content, '<< >>')
    document.update_stream(content, '\n'.join(f'q 595 0 0 842 0 0 cm 0 g /Im{i} Do Q'
                                              for i in range(len(xrefs))).encode())
    document.xref_set_key(page.xref, 'Contents', f'{content} 0 R')


def _stencil(document, image):
    mask = image.convert('L').point(lambda v: 255 if v > 160 else 0).convert('1')
    xref = document.get_new_xref()
    document.update_object(xref, f'<< /Type /XObject /Subtype /Image /Width {mask.width} /Height {mask.height} '
                                 '/ImageMask true /BitsPerComponent 1 >>')
    document.update_stream(xref, mask.tobytes())
    return xref


def _rgb(document, image):
    xref = document.get_new_xref()
    document.update_object(xref, f'<< /Type /XObject /Subtype /Image /Width {image.width} /Height {image.height} '
                                 '/ColorSpace /DeviceRGB /BitsPerComponent 8 >>')
    document.update_stream(xref, image.convert('RGB').tobytes())
    return xref


def build(path, kind):
    import pymupdf
    from PIL import Image
    document = pymupdf.open()
    if kind == 'plain':
        _image_page(document)
    elif kind == 'hidden':
        page = _image_page(document)
        page.insert_text((40, 60), 'Xq3 zz9 lorem ipsum dolor sit amet consectetur adipiscing 12345 6789',
                         fontsize=8, render_mode=3, fontname='helv')
    elif kind == 'few':
        page = _image_page(document)
        page.insert_text((500, 820), '1 / 1', fontsize=8, fontname='helv')
    elif kind == 'later':
        _image_page(document)
        document.new_page(width=595, height=842).insert_text(
            (40, 80), 'Page two text layer content ' * 4, fontsize=9, fontname='helv')
    elif kind == 'stencil':
        _raw_page(document, [_stencil(document, _picture())])
    elif kind == 'mrc':
        paper = Image.new('RGB', (1200, 1696), (236, 232, 222))
        _raw_page(document, [_rgb(document, paper), _stencil(document, _picture())])
    elif kind == 'smask':
        gray = _picture().convert('L')
        alpha = gray.point(lambda v: 255 - v)
        rgba = Image.merge('RGBA', (Image.new('L', gray.size, 0),) * 3 + (alpha,))
        document.new_page(width=595, height=842).insert_image(pymupdf.Rect(0, 0, 595, 842), stream=_png(rgba))
    else:
        raise AssertionError(kind)
    document.save(path)
    document.close()
    return path


def _half(words, left):
    """Squeeze a portrait page into the left or right half of a sheet (page-% coordinates)."""
    out = []
    for word in words:
        x0, y0, x1, y1 = word.bbox_px
        shift = 0 if left else W / 2
        out.append(type(word)(word.text, word.confidence, (x0 / 2 + shift, y0, x1 / 2 + shift, y1)))
    return out


def _page(index, total, doc_no='1234-5678-9012-34567'):
    words = header(index, total) + table_head(31.8) + row(34.4, index, '전북특별자치도 전주시 가상동', '2020-01-01')
    for word in words:
        if word.text.startswith('문서확인번호'):
            word.text = f'문서확인번호 : {doc_no}'
    return words


def sheet(*pages):
    words = []
    for left, page in zip((True, False), pages):
        words += _half(page, left)
    return PageImage(0, PageSource.EMBEDDED, (842.0, 595.0), pixel_size=(W, H)), OcrResult('own', words)

