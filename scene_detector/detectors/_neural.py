from __future__ import annotations

import subprocess
from pathlib import Path


def read_small_frames(path, width=48, height=27, total=None, progress=True, desc="[decode] frames"):
    """Estrae tutti i frame ridimensionati a (height, width) via ffmpeg.

    Legge la pipe rgb24 in streaming mostrando una progress bar (total = n_frames noti).
    Ritorna un array uint8 di shape [N, height, width, 3]. A 48x27 sono ~3.9 KB/frame
    (es. film 2h @24fps ~ 1.2 GB in RAM).
    """
    import numpy as np
    from tqdm import tqdm

    frame_size = width * height * 3
    cmd = [
        "ffmpeg", "-i", str(Path(path)),
        "-vf", f"scale={width}:{height}",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-loglevel", "error", "pipe:1",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    chunks = []
    bar = tqdm(total=total, unit="f", unit_scale=True, desc=desc, disable=not progress)
    try:
        while True:
            data = proc.stdout.read(frame_size * 512)
            if not data:
                break
            chunks.append(data)
            bar.update(len(data) // frame_size)
    finally:
        bar.close()
        proc.stdout.close()
        ret = proc.wait()
    if ret != 0:
        raise subprocess.CalledProcessError(ret, cmd)
    return np.frombuffer(b"".join(chunks), np.uint8).reshape(-1, height, width, 3)


def probs_to_ranges(probs, threshold=0.5, min_scene_len=15):
    """Prob boundary per-frame -> lista di (start, end) inclusivi, contigui, copre tutti i frame."""
    n = len(probs)
    ranges = []
    start = 0
    for i in range(n):
        if probs[i] >= threshold and (i - start + 1) >= min_scene_len:
            ranges.append((start, i))
            start = i + 1
    if start <= n - 1:
        ranges.append((start, n - 1))
    elif not ranges:
        ranges.append((0, max(0, n - 1)))
    return ranges
