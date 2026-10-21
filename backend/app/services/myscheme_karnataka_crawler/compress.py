from __future__ import annotations

from io import BytesIO
from typing import Tuple


def try_lossless_compress_pdf(data: bytes) -> Tuple[bytes, int, int]:
    """Rewrite PDF streams; keep smaller file only."""
    original = len(data)
    try:
        import pypdf

        reader = pypdf.PdfReader(BytesIO(data))
        writer = pypdf.PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        for page in writer.pages:
            try:
                page.compress_content_streams()
            except Exception:
                pass
        buf = BytesIO()
        writer.write(buf)
        compressed = buf.getvalue()
        if len(compressed) < original:
            return compressed, original, original - len(compressed)
    except Exception:
        pass
    return data, original, 0
