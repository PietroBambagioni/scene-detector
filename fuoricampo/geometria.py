"""Di quanto il film è ricadrato rispetto al girato — misurato, non stimato a occhio.

I primi match trovati sono veri ma correlano 0,80 dove due copie della stessa immagine
dovrebbero stare a 0,98: guardandoli affiancati si vede perché — il girato mostra più campo,
il montato è più stretto. Finché le due impronte guardano due porzioni diverse
dell'inquadratura, la somiglianza resta bassa e la maggior parte dei riusi non emerge.

Qui si prende una manciata di coppie già confermate a occhio e si cerca, su una griglia, lo
zoom e lo spostamento che massimizzano la correlazione. Il valore che ne esce è il crop da
usare sul girato perché le due impronte inquadrino la stessa cosa.

    .venv/bin/python fuoricampo/geometria.py
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from scipy.ndimage import zoom as ndzoom

from impronta import CROP, LATO
from verifica import FILM, GIRATO

RIS = 256   # risoluzione a cui si estraggono i due frame, prima di provare i ritagli

# Coppie confermate guardando i fotogrammi affiancati (`fuoricampo/README.md`):
# (secondo nel film, parte, secondo nella parte)
COPPIE = [
    (126.8 * 60, 4, 7.3 * 60), (206.8 * 60, 4, 187.0 * 60), (172.8 * 60, 4, 107.5 * 60),
    (183.3 * 60, 4, 114.2 * 60), (104.7 * 60, 3, 117.5 * 60), (21.3 * 60, 3, 174.5 * 60),
    (73.9 * 60, 5, 98.2 * 60), (147.8 * 60, 3, 153.4 * 60), (112.3 * 60, 2, 130.7 * 60),
    (110.2 * 60, 2, 125.5 * 60),
]


def frame(path: Path, t: float, crop: str) -> np.ndarray:
    return sequenza(path, t, crop, 1, 1)[0]


def sequenza(path: Path, t0: float, crop: str, n: int, fps: float) -> np.ndarray:
    """`n` frame consecutivi a `fps`, a partire da `t0`. Un solo ffmpeg invece di n seek.

    Serve perché il centro del segmento nel film e quello nel girato non sono lo stesso
    istante: il voting li allinea a ±1 s, e su un secondo di parlato l'inquadratura cambia
    abbastanza da falsare qualsiasi stima geometrica. Il tempo va cercato insieme allo zoom.
    """
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{max(t0,0):.2f}", "-i", str(path),
         "-frames:v", str(n), "-vf", f"fps={fps},crop={crop},scale={RIS}:{RIS}",
         "-pix_fmt", "gray", "-f", "rawvideo", "pipe:1"], capture_output=True).stdout
    a = np.frombuffer(raw, np.uint8)
    k = len(a) // (RIS * RIS)
    return a[:k * RIS * RIS].reshape(k, RIS, RIS).astype(np.float32)


def piccolo(img: np.ndarray) -> np.ndarray:
    """Riduce a LATO×LATO e normalizza, come fa l'impronta."""
    v = ndzoom(img, LATO / img.shape[0], order=1).reshape(-1)[:LATO * LATO]
    v = v - v.mean()
    n = np.linalg.norm(v)
    return v / n if n > 1e-6 else v


def cerca(a: np.ndarray, bs: np.ndarray):
    """Istante, zoom e spostamento, fra i frame `bs`, che massimizzano la correlazione con `a`."""
    va = piccolo(a)
    best = (-1.0, 1.0, 0.0, 0.0, 0)
    for k, b in enumerate(bs):
        best = max(best, _cerca_uno(va, b) + (k,))
    return best


def _cerca_uno(va: np.ndarray, b: np.ndarray):
    best = (-1.0, 1.0, 0.0, 0.0)
    for z in np.arange(0.70, 1.021, 0.02):
        lato = int(RIS * z)
        for dx in np.arange(-0.10, 0.101, 0.02):
            for dy in np.arange(-0.10, 0.101, 0.02):
                x0 = int((RIS - lato) / 2 + dx * RIS)
                y0 = int((RIS - lato) / 2 + dy * RIS)
                if x0 < 0 or y0 < 0 or x0 + lato > RIS or y0 + lato > RIS:
                    continue
                c = float(va @ piccolo(b[y0:y0 + lato, x0:x0 + lato]))
                if c > best[0]:
                    best = (c, z, dx, dy)
    return best


if __name__ == "__main__":
    FIN, PASSO = 6.0, 5.0     # 6 s di girato attorno al punto, 5 frame al secondo
    stime = []
    for tf, parte, tg in COPPIE:
        nome = f"Fuori campo di Anna - {parte}"
        a = frame(FILM, tf, CROP["Anna"])
        bs = sequenza(GIRATO / f"{nome}.mp4", tg - FIN / 2, CROP[nome], int(FIN * PASSO), PASSO)
        c0 = float(piccolo(a) @ piccolo(bs[len(bs) // 2]))
        c, z, dx, dy, k = cerca(a, bs)
        stime.append((z, dx, dy, c, c0))
        print(f"  film {tf/60:6.1f} min · FC{parte} {tg/60:6.1f} min   "
              f"corr {c0:.3f} → {c:.3f}   zoom {z:.2f}  dx {dx:+.2f}  dy {dy:+.2f}  "
              f"t {k/PASSO - FIN/2:+.1f}s")

    s = np.array(stime)
    buone = s[s[:, 3] > 0.75]
    print(f"\n{len(buone)}/{len(s)} coppie sopra 0,75 dopo l'allineamento")
    if len(buone):
        print(f"zoom mediano {np.median(buone[:,0]):.3f} · dx {np.median(buone[:,1]):+.3f} · "
              f"dy {np.median(buone[:,2]):+.3f}")
        print(f"correlazione mediana: {np.median(buone[:,4]):.3f} → {np.median(buone[:,3]):.3f}")
