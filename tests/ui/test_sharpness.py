"""Pages must stay sharp on screens set to 100 %, 125 % and 150 %."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

CHECK = Path(__file__).with_name("sharpness_check.py")


@pytest.mark.parametrize("scale", ["1", "1.25", "1.5"])
@pytest.mark.parametrize("name", ["boe.pdf", "escaneado.pdf"])
def test_pages_reach_the_screen_pixel_for_pixel(sample, scale, name):
    result = subprocess.run(
        [sys.executable, str(CHECK), str(sample(name))],
        env={**os.environ, "QT_SCALE_FACTOR": scale, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"scale={float(scale)}" in result.stdout, "the screen scale was not applied"
