import shutil
import subprocess

import pytest

from scene_detector.io.video import probe

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg non disponibile")


def _make_video(path, seconds=2, fps=25, w=320, h=240):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=size={w}x{h}:rate={fps}",
         "-t", str(seconds), "-pix_fmt", "yuv420p", "-loglevel", "error", str(path)],
        check=True,
    )


def test_probe_reads_metadata(tmp_path):
    v = tmp_path / "clip.mp4"
    _make_video(v, seconds=2, fps=25, w=320, h=240)
    info = probe(v)
    assert info.width == 320 and info.height == 240
    assert abs(info.fps - 25.0) < 1e-6
    assert abs(info.duration - 2.0) < 0.2
    assert abs(info.n_frames - 50) <= 2  # nb_frames o fallback round(duration*fps)
