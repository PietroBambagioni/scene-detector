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

    # `nb_frames` è un metadato del **container** e sa mentire: su un file tagliato con `-c copy`
    # conta i pacchetti del GOP originale, non i frame che restano. Su `clips/Anna/scene-308.mp4`
    # dice 774 dove `-count_frames` ne trova 753 e il decode ne consegna 754 — che è esattamente
    # `duration × fps`. Sui film interi i due numeri coincidono, quindi si prende il **minimo**:
    # mai promettere frame che non esistono, e contarli per davvero costerebbe una passata di
    # decode del film intero.
    nb = st.get("nb_frames")
    n_frames = round(duration * fps)
    if nb and nb != "N/A":
        n_frames = min(n_frames, int(nb))

    return VideoInfo(path, fps, n_frames, duration, int(st["width"]), int(st["height"]))
