from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..core.config import SplitMode
from ..core.cpu import resolve_workers


def split(video, scenes, output_dir, mode=SplitMode.copy, jobs=0):
    """Esporta ogni Scene come clip via ffmpeg, in parallelo su più core. -> clip orfane.

    - `copy`: veloce ma taglio sui keyframe (±GOP).
    - `reencode`: frame-accurate (H.264 CRF 18 / AAC), 1 thread per clip.
    `jobs` = processi ffmpeg paralleli (0 = auto: tutti i core meno 2).

    Un run che produce **meno** shot di quello prima (una soglia più alta, un'unione fatta nella
    UI) lascerebbe su disco le clip in eccesso: nome legittimo, contenuto ormai dentro un'altra
    clip, nessun manifest che le citi. Vengono rinominate `.orfano` — non cancellate, così restano
    da guardare, e `scene-*.mp4` non le ripesca al run dopo.
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

    # Confronto sul **numero**, non `sorted(...)[len(scenes):]`: il template è `{:03d}` ma un film
    # con più di 999 shot passa a 4 cifre (*Rogue One* ne ha 3204), e in ordine lessicografico
    # `scene-1000.mp4` viene prima di `scene-999.mp4`.
    orfane = 0
    for vecchia in out.glob("scene-*.mp4"):
        n = vecchia.stem.split("-")[-1]
        if n.isdigit() and int(n) > len(scenes):
            vecchia.replace(vecchia.parent / (vecchia.name + ".orfano"))
            orfane += 1
    return orfane
