import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
LIB = ROOT / "firmware" / "ring-esp32s3" / "lib"


@pytest.fixture(scope="session")
def c_tool(tmp_path_factory):
    """Compile the firmware C libraries into a small host CLI (skips if no C compiler)."""
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if not cc:
        pytest.skip("no C compiler")
    out = tmp_path_factory.mktemp("c") / "morse_cli"
    src = [
        str(pathlib.Path(__file__).parent / "ctools" / "morse_cli.c"),
        str(LIB / "mcring_morse" / "mcring_morse.c"),
        str(LIB / "mcring_proto" / "mcring_proto.c"),
        str(LIB / "mcring_adpcm" / "mcring_adpcm.c"),
    ]
    inc = [f"-I{LIB / d}" for d in ("mcring_morse", "mcring_proto", "mcring_adpcm")]
    subprocess.run([cc, "-std=c99", "-O1", "-Wall", "-Werror", *inc, *src, "-o", str(out)], check=True)
    return out
