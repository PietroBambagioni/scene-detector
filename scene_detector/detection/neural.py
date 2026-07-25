from __future__ import annotations

import subprocess
from pathlib import Path

from ..core.scene import scenes_from_ranges


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
    (es. film 2h @24fps ~ 1.2 GB in RAM).
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


def runs_to_ranges(probs, threshold=0.05):
    """Prob per-frame -> (ranges contigui, transizioni). Come `probs_to_ranges`, ma non
    scambia una dissolvenza per una fila di tagli.

    `probs_to_ranges` chiude uno shot a **ogni** frame sopra soglia: durante una dissolvenza i
    frame caldi sono molti e consecutivi, quindi produce una fila di scene da 1 frame che
    `enforce_min_len` poi rifonde. La larghezza della transizione è nelle `probs` e la buttiamo
    noi. Qui una **corsa contigua** di frame caldi è *una* transizione: lo shot uscente la
    include e finisce a `j`, quello entrante parte a `j+1`.

    I range restano contigui e coprono tutti i frame — stesso contratto di `probs_to_ranges`,
    quindi `boundary_confidences` e lo splitter non cambiano. Ciò che si
    guadagna è il secondo valore: `transitions[k]` è l'intervallo `(start, end)` della giunta
    che **apre** `ranges[k]`, oppure `None` per il primo shot e per gli stacchi netti (corsa da
    un frame solo, dove non c'è larghezza da riportare).

    Misurato su ClipShots (1634 transizioni reali con il range annotato): a soglia 0,05 il
    recall passa da 0,088 a 0,325, e sui soli stacchi netti *migliora* — 0,95 contro 0,81 —
    quindi non è un baratto fra graduali e cut.
    """
    n = len(probs)
    hot = [i for i in range(n) if probs[i] >= threshold]
    if not hot:
        return [(0, max(0, n - 1))], [None]

    runs, start = [], hot[0]
    for prev, cur in zip(hot, hot[1:]):
        if cur != prev + 1:
            runs.append((start, prev))
            start = cur
    runs.append((start, hot[-1]))

    ranges = []
    pos = 0
    for _a, b in runs:
        ranges.append((pos, b))
        pos = b + 1
    if pos <= n - 1:
        ranges.append((pos, n - 1))

    # la giunta che apre `ranges[k]` è la corsa `k-1`: il primo shot non ne ha una a monte, e
    # una corsa da un frame solo è uno stacco netto, che non ha larghezza da riportare
    transitions = [None]
    for a, b in runs[:len(ranges) - 1]:
        transitions.append((a, b) if b > a else None)
    return ranges, transitions


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


# ---------------------------------------------------------------- detector -----

class NeuralDetector:
    """Detector neurale: decodifica a 27x48, inference a finestre, probs -> scene.

    La sottoclasse fornisce solo il predictor e il nome.
    """

    name = ""
    input_size = (27, 48)  # (H, W)

    def __init__(self, weights=None, threshold=0.05):
        self.weights = Path(weights) if weights else None
        self.threshold = threshold
        self.probs = None  # prob boundary per-frame dell'ultima detection

    def detect(self, video):
        h, w = self.input_size
        frames = read_small_frames(video.path, w, h, total=video.n_frames,
                                   desc=f"[{self.name}] frames")
        return self.detect_from_frames(frames, video)

    def detect_from_frames(self, frames, video):
        """Predizione da frame già decodificati (uint8[N,27,48,3])."""
        self.probs = self._predictor().predict(frames)  # float[N]
        ranges, transitions = runs_to_ranges(self.probs, self.threshold)
        return scenes_from_ranges(ranges, video.fps, self.name,
                                  boundary_confidences(ranges, self.probs), transitions)

    def _predictor(self):
        try:
            import torch  # noqa: F401
        except ImportError as e:
            raise RuntimeError(f"{self.name} richiede torch: pip install '.[neural]'") from e
        if self.weights is None or not self.weights.exists():
            raise RuntimeError(f"Pesi {self.name} mancanti: lancia `scene-detector-setup` "
                               f"(oppure passa --{self.name}-weights PATH).")
        return self._build()

    def _build(self):
        raise NotImplementedError


class TransNetV2Detector(NeuralDetector):
    """Detector primario (shot boundary neurale)."""

    name = "transnet"

    def _build(self):
        from .models.wrapper import TransNetV2Predictor
        return TransNetV2Predictor(self.weights)
