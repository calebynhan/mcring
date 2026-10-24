"""Image normalisation: sniff type, downscale huge uploads, fix EXIF rotation, re-encode as JPEG."""
from __future__ import annotations

import io

from PIL import Image, ImageOps


def sniff_media_type(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return None


def normalise(data: bytes, max_edge: int = 1024) -> tuple[bytes, str, tuple[int, int]]:
    """Return (bytes, media_type, (w, h)). Small JPEGs pass through untouched."""
    mt = sniff_media_type(data)
    if mt is None:
        raise ValueError("unsupported or corrupt image")
    img = Image.open(io.BytesIO(data))
    img.load()
    w, h = img.size
    if mt == "image/jpeg" and max(w, h) <= max_edge:
        return data, mt, (w, h)
    img = ImageOps.exif_transpose(img)
    if max(img.size) > max_edge:
        img.thumbnail((max_edge, max_edge))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88)
    return out.getvalue(), "image/jpeg", img.size
