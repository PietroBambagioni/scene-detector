from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..core.config import SplitMode
from ..core.cpu import resolve_workers


def split(video, scenes, output_dir, mode=SplitMode.copy, jobs=0):
    """Esporta ogni Scene come clip via ffmpeg, in parallelo su più core.

    - `copy`: veloce ma taglio sui keyframe (±GOP).
    - `reencode`: frame-accurate (H.264 CRF 18 / AAC), 1 thread per clip.
    `jobs` = processi ffmpeg paralleli (0 = auto: tutti i core meno 2).
    """
    from tqdm import tqdm

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    workers = resolve_workers(jobs)

    def clip_cmd(s):
        start = s.start_frame / video.fps
        dur = (s.end_frame + 1) / video.fps - start
        dst = out / f"scene-{s.index + 1:03d}.mp4"
        cmd = ["ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(video.path), "-t", f"{dur:.3f}", "-map", "0"]
        if mode == SplitMode.copy:
            cmd += ["-c", "copy"]
        else:
            cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-threads", "1"]
        return cmd + ["-loglevel", "error", str(dst)]

    def run_one(s):
        subprocess.run(clip_cmd(s), check=True)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(tqdm(ex.map(run_one, scenes), total=len(scenes),
                  desc=f"[split] {mode.value} ×{workers}", unit="clip"))
