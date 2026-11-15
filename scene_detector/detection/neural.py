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


def runs_to_ranges(probs, threshold=0.05, min_peak=0.0):
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

    `min_peak` **separa due domande che `threshold` da solo confonde**: la soglia dice *dove
    comincia e finisce* una transizione, `min_peak` dice *se esiste*. Una corsa il cui frame più
    caldo non arriva a `min_peak` non produce un confine e viene assorbita nello shot: i suoi
    frame restano coperti, il contratto non cambia.

    Serve su materiale degradato, dove il rumore del supporto produce corse larghe e tiepide che
    la sola soglia non distingue da una dissolvenza. Misurato sul restauro di *Anna* (Portapak
    1975): le corse col picco sotto 0,50 sono **6× più frequenti** che su un film pulito
    (2,28 per stacco sicuro contro 0,38) e in un campione cieco **0 su 24 erano stacchi veri**,
    contro 12 su 12 dei controlli (`prove/annota_deboli.py`). Vedi `plan/VERBALE.md` §3.6.

    ⚠️ **Default 0,0 — disattivato, e deve restarlo.** Su un film pulito quelle stesse corse
    tiepide sono in buona parte stacchi legittimi che a soglia alta non vedevamo (su *Rogue One*
    sono 933 e non sono mai state annotate). È una taratura per materiale, non un miglioramento
    universale.
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

    if min_peak:
        runs = [(a, b) for a, b in runs if max(probs[a:b + 1]) >= min_peak]
        if not runs:
            return [(0, max(0, n - 1))], [None]

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


def cover_exactly(ranges, transitions, n_frames):
    """Forza i range a coprire esattamente `n_frames`. -> (ranges, transitions).

    **`ffmpeg` e `ffprobe` non sempre concordano su quanti frame ha un file.** Su *Anna* il decode
    ne consegna 320737 dove `duration × fps` ne dà 320735, quindi l'ultimo shot sforava di 2 e
    `_shots_corretti` **rifiutava il manifest che la pipeline aveva appena scritto** — cioè
    `--from-manifest` non funzionava su quel catalogo. Su *Rogue One* i due numeri coincidono e il
    difetto non si vedeva.

    Il numero che vale è quello di `probe`: manifest, splitter, miniature e UI si appoggiano a lui.
    Vale in entrambe le direzioni — se il decode consegna *meno* frame, l'ultimo shot si allunga
    fino alla fine invece di lasciare un buco.
    """
    keep = [i for i, (s, _) in enumerate(ranges) if s <= n_frames - 1] or [0]
    ranges = [ranges[i] for i in keep]
    transitions = [transitions[i] for i in keep]
    ranges[-1] = (ranges[-1][0], n_frames - 1)
    return ranges, transitions


def boundary_confidences(ranges, probs, transitions=None):
    """Confidenza continua per shot = il **picco** di prob della giunta che lo apre.

    Uno stacco netto è una corsa da un frame, il frame `s-1`: la confidenza è `probs[s-1]`. Una
    transizione graduale (`transitions[i]`, da `runs_to_ranges`) è una corsa di più frame, e la
    confidenza è il suo massimo — la stessa grandezza con cui `min_peak` decide se il taglio
    esiste. Il primo shot (inizio film, nessun taglio a monte) ha confidenza 1.0.

    Leggeva `probs[s-1]` anche sulle graduali, cioè l'**ultimo** frame della corsa: quello appena
    sopra la soglia, per costruzione. Su *Anna* le 48 graduali avevano confidenza mediana 0,10
    contro un picco mediano di 0,675, e i 41 shot «incerti» della coda di revisione erano tutti
    graduali col picco sopra 0,5. Su *Rogue One* 510 graduali su 515 finivano sotto 0,5, col
    picco sotto 0,5 solo in 284. La coda ordinava per larghezza della transizione, non per dubbio.
    """
    n = len(probs)
    confs = []
    for i, (start, _end) in enumerate(ranges):
        tr = transitions[i] if transitions else None
        if i == 0 or start <= 0:
            confs.append(1.0)
        elif tr:
            confs.append(float(max(probs[tr[0]:tr[1] + 1])))
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

    def __init__(self, weights=None, threshold=0.05, min_peak=0.0):
        self.weights = Path(weights) if weights else None
        self.threshold = threshold
        self.min_peak = min_peak
        self.probs = None  # prob boundary per-frame dell'ultima detection
        self._pred = None  # modello costruito, memoizzato: `prove/` cicla su centinaia di video

    def detect(self, video):
        self._predictor()  # pesi mancanti: fallisci ora, non dopo 2,5 min di decodifica
        h, w = self.input_size
        frames = read_small_frames(video.path, w, h, total=video.n_frames,
                                   desc=f"[{self.name}] frames")
        return self.detect_from_frames(frames, video)

    def detect_from_frames(self, frames, video):
        """Predizione da frame già decodificati (uint8[N,27,48,3])."""
        self.probs = self._predictor().predict(frames)  # float[N]
        ranges, transitions = runs_to_ranges(self.probs, self.threshold, self.min_peak)
        ranges, transitions = cover_exactly(ranges, transitions, video.n_frames)
        confs = boundary_confidences(ranges, self.probs, transitions)
        return scenes_from_ranges(ranges, video.fps, self.name, confs, transitions)

    def _predictor(self):
        try:
            import torch  # noqa: F401
        except ImportError as e:
            raise RuntimeError(f"{self.name} richiede torch: pip install '.[neural]'") from e
        if self.weights is None or not self.weights.exists():
            raise RuntimeError(f"Pesi {self.name} mancanti: lancia `scene-detector-setup` "
                               f"(oppure passa --{self.name}-weights PATH).")
        if self._pred is None:
            self._pred = self._build()
        return self._pred

    def _build(self):
        raise NotImplementedError


class TransNetV2Detector(NeuralDetector):
    """Detector primario (shot boundary neurale)."""

    name = "transnet"

    def _build(self):
        from .models.wrapper import TransNetV2Predictor
        return TransNetV2Predictor(self.weights)


class AutoShotDetector(NeuralDetector):
    """[OPZIONALE] Seconda opinione neurale (NAS-based). Stesso contratto di TransNetV2."""

    name = "autoshot"

    def _build(self):
        from .models.wrapper import AutoShotPredictor
        return AutoShotPredictor(self.weights)
