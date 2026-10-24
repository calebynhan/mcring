import io
import os
import sys
import pathlib

import pytest
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("MCRING_API_TOKEN", "")


@pytest.fixture
def jpeg_bytes():
    img = Image.new("RGB", (320, 240), (200, 30, 90))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


@pytest.fixture
def big_png_bytes():
    img = Image.new("RGB", (3000, 2000), (10, 200, 90))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
