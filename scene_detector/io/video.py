from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VideoInfo:
    path: Path
    fps: float
    n_frames: int
    duration: float
    width: int
    height: int


def probe(path) -> VideoInfo:
    """Legge i metadati del video via ffprobe."""
    path = Path(path)
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate,nb_frames,width,height,duration",
        "-show_entries", "format=duration",
        "-of", "json", str(path),
    ]
    out = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
    st = out["streams"][0]

    num, den = st["r_frame_rate"].split("/")
    fps = float(num) / float(den)
    duration = float(st.get("duration") or out["format"]["duration"])

    nb = st.get("nb_frames")
    n_frames = int(nb) if nb and nb != "N/A" else round(duration * fps)

    return VideoInfo(path, fps, n_frames, duration, int(st["width"]), int(st["height"]))
