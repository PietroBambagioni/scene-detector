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


def test_probe_non_si_fida_di_nb_frames_gonfiato(tmp_path):
    """Una clip tagliata con `-c copy` porta un `nb_frames` che conta i pacchetti del GOP
    originale: 85 dove i frame veri sono ~52. È il caso di ogni clip prodotta da `split`, che è
    un input legittimo — e `n_frames` sovrastimato sfonda il contratto «i range coprono tutti i
    frame», perché i range coprono quelli **decodificati**.
    """
    src = tmp_path / "src.mp4"
    _make_video(src, seconds=6, fps=25)
    cut = tmp_path / "cut.mp4"
    subprocess.run(["ffmpeg", "-y", "-ss", "1.3", "-i", str(src), "-t", "2", "-c", "copy",
                    "-loglevel", "error", str(cut)], check=True)

    info = probe(cut)
    assert abs(info.n_frames - round(info.duration * info.fps)) <= 1
    assert info.n_frames < 70          # il metadato del container ne dichiarava 85


def test_probe_reads_metadata(tmp_path):
    v = tmp_path / "clip.mp4"
    _make_video(v, seconds=2, fps=25, w=320, h=240)
    info = probe(v)
    assert info.width == 320 and info.height == 240
    assert abs(info.fps - 25.0) < 1e-6
    assert abs(info.duration - 2.0) < 0.2
    assert abs(info.n_frames - 50) <= 2  # nb_frames o fallback round(duration*fps)
