from __future__ import annotations

import subprocess
from pathlib import Path


def _ffmpeg_cmd(path, width, height):
    return [
        "ffmpeg", "-i", str(Path(path)),
        "-vf", f"scale={width}:{height}",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-loglevel", "error", "pipe:1",
    ]


def read_small_frames(path, width=48, height=27, total=None, progress=True, desc="[decode] frames"):
    """Estrae tutti i frame ridimensionati a (height, width) via ffmpeg.

    Legge la pipe rgb24 in streaming mostrando una progress bar (total = n_frames noti).
    Ritorna un array uint8 di shape [N, height, width, 3]. A 48x27 sono ~3.9 KB/frame
    (es. film 2h @24fps ~ 1.2 GB in RAM). Per RAM limitata vedi `iter_small_windows`.
    """
    import numpy as np
    from tqdm import tqdm

    frame_size = width * height * 3
    proc = subprocess.Popen(_ffmpeg_cmd(path, width, height), stdout=subprocess.PIPE)
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
        raise subprocess.CalledProcessError(ret, _ffmpeg_cmd(path, width, height))
    return np.frombuffer(b"".join(chunks), np.uint8).reshape(-1, height, width, 3)


class FrameWindower:
    """Trasforma un iteratore di frame reali nelle finestre da 100 dell'inference TransNet.

    Replica esattamente il padding ufficiale (25 frame di testa = primo frame, coda = ultimo
    frame fino al multiplo giusto) e produce finestre da 100 frame a passo 50, senza mai
    materializzare tutti i frame: in RAM vive solo la finestra corrente (~100 frame).
    Espone `.n` (numero di frame reali) a iterazione conclusa, per il trim finale `[:n]`.
    """

    WIN, STEP, LEAD = 100, 50, 25

    def __init__(self, frames):
        self._frames = iter(frames)
        self.n = 0

    def __iter__(self):
        import numpy as np

        def padded():
            it = self._frames
            first = next(it, None)
            if first is None:
                return
            for _ in range(self.LEAD):
                yield first
            self.n = 1
            prev = first
            yield first
            for fr in it:
                self.n += 1
                yield fr
                prev = fr
            pad_end = self.LEAD + self.STEP - (self.n % self.STEP or self.STEP)
            for _ in range(pad_end):
                yield prev

        buf = []
        for pf in padded():
            buf.append(pf)
            if len(buf) == self.WIN:
                yield np.stack(buf)
                buf = buf[self.STEP:]


def _pipe_frames(path, width, height, total, progress, desc):
    """Generatore di frame uint8[height,width,3] letti dalla pipe ffmpeg, con progress bar."""
    import numpy as np
    from tqdm import tqdm

    frame_size = width * height * 3
    proc = subprocess.Popen(_ffmpeg_cmd(path, width, height), stdout=subprocess.PIPE)
    bar = tqdm(total=total, unit="f", unit_scale=True, desc=desc, disable=not progress)
    try:
        leftover = b""
        while True:
            block = proc.stdout.read(frame_size * 512)
            if not block:
                break
            data = leftover + block
            nfull = len(data) // frame_size
            for i in range(nfull):
                yield np.frombuffer(data, np.uint8, count=frame_size,
                                    offset=i * frame_size).reshape(height, width, 3)
                bar.update(1)
            leftover = data[nfull * frame_size:]
    finally:
        bar.close()
        proc.stdout.close()
        ret = proc.wait()
    if ret != 0:
        raise subprocess.CalledProcessError(ret, _ffmpeg_cmd(path, width, height))


def stream_small_windows(path, width=48, height=27, total=None, progress=True,
                         desc="[decode] stream"):
    """Streaming windowed: `FrameWindower` sui frame letti dalla pipe ffmpeg.

    Iterabile che produce le finestre uint8[100,height,width,3]; `.n` è il numero di frame
    reali (disponibile a fine iterazione). RAM da GB a MB rispetto a `read_small_frames`.
    """
    return FrameWindower(_pipe_frames(path, width, height, total, progress, desc))


def probs_to_ranges(probs, threshold=0.5):
    """Prob boundary per-frame -> lista di (start, end) inclusivi, contigui, copre tutti i frame.

    Traduce solo prob->range: ogni frame con prob >= threshold chiude una scena. Il vincolo di
    lunghezza minima è applicato a valle da `enforce_min_len` (unica autorità su `min_scene_len`).
    """
    n = len(probs)
    ranges = []
    start = 0
    for i in range(n):
        if probs[i] >= threshold:
            ranges.append((start, i))
            start = i + 1
    if start <= n - 1:
        ranges.append((start, n - 1))
    elif not ranges:
        ranges.append((0, max(0, n - 1)))
    return ranges


def boundary_confidences(ranges, probs):
    """Confidenza continua per shot = prob boundary per-frame del taglio che lo apre.

    Il taglio che apre lo shot con `start_frame = s` è il frame `s-1` (dove la prob supera la
    soglia in `probs_to_ranges`), quindi la confidenza dello shot è `probs[s-1]`. Il primo shot
    (inizio film, nessun taglio a monte) ha confidenza 1.0. Sostituisce il flag binario 1.0/0.5.
    """
    n = len(probs)
    confs = []
    for i, (start, _end) in enumerate(ranges):
        if i == 0 or start <= 0:
            confs.append(1.0)
        else:
            confs.append(float(probs[min(start - 1, n - 1)]))
    return confs
