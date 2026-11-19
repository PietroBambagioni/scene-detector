"""Riverifica ogni segmento a piena risoluzione, invece di fidarsi dell'impronta.

Il match lavora su 24×24 pixel e quattro campioni al secondo: serve a cercare in fretta dentro
quindici ore, non a decidere. Qui ogni segmento viene ripreso a 128×128 e si cerca la
**geometria** che lo allinea davvero — zoom e spostamento, come in `geometria.py`, perché il
film è ricadrato rispetto al girato in modo diverso da ripresa a ripresa — insieme all'istante
esatto, dato che i confini valgono ±1 s.

Il punteggio che ne esce è confrontabile fra segmenti e dice quali reggono e quali no.

    .venv/bin/python fuoricampo/controllo.py [n_segmenti]   # senza argomenti: tutti
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import zoom as ndzoom

from impronta import CROP, LATO
from timeline import GIRATO, QUI
from verifica import FILM

RIS = 128          # risoluzione di lavoro: 256 non cambiava il verdetto e costava il quadruplo
FIN, PASSO = 3.0, 4.0     # secondi di girato attorno al punto, e frame al secondo
ZOOM = np.arange(0.62, 1.021, 0.04)      # 0,62 e 0,66 in più: in geometria.py diversi
                                          # ottimi cadevano sul bordo inferiore della griglia
SPOSTA = np.arange(-0.08, 0.081, 0.04)


def frame(path: Path, t0: float, crop: str, n: int) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{max(t0,0):.2f}", "-i", str(path),
         "-frames:v", str(n), "-vf", f"fps={PASSO},crop={crop},scale={RIS}:{RIS}",
         "-pix_fmt", "gray", "-f", "rawvideo", "pipe:1"], capture_output=True).stdout
    a = np.frombuffer(raw, np.uint8)
    k = len(a) // (RIS * RIS)
    return a[:k * RIS * RIS].reshape(k, RIS, RIS).astype(np.float32)


def vettore(img: np.ndarray) -> np.ndarray:
    v = ndzoom(img, LATO / img.shape[0], order=1).reshape(-1)[:LATO * LATO]
    v = v - v.mean()
    n = np.linalg.norm(v)
    return v / n if n > 1e-6 else v


def meglio(a: np.ndarray, bs: np.ndarray) -> tuple[float, float, int]:
    """Correlazione massima fra il frame `a` e i frame `bs`, su zoom e spostamento."""
    va = vettore(a)
    top, zoom_top, k_top = -1.0, 1.0, 0
    for k, b in enumerate(bs):
        for z in ZOOM:
            lato = int(RIS * z)
            for dx in SPOSTA:
                for dy in SPOSTA:
                    x0 = int((RIS - lato) / 2 + dx * RIS)
                    y0 = int((RIS - lato) / 2 + dy * RIS)
                    if x0 < 0 or y0 < 0 or x0 + lato > RIS or y0 + lato > RIS:
                        continue
                    c = float(va @ vettore(b[y0:y0 + lato, x0:x0 + lato]))
                    if c > top:
                        top, zoom_top, k_top = c, z, k
    return top, zoom_top, k_top


def controlla(seg: dict, istanti: int = 2) -> dict:
    """Prende `istanti` punti dentro il segmento e li riverifica uno per uno."""
    nome = f"Fuori campo di Anna - {seg['parte']}"
    dur = seg["film_end"] - seg["film_start"]
    punti = [seg["film_start"] + dur * f for f in np.linspace(0.3, 0.7, istanti)]
    esiti, zoom = [], []
    for tf in punti:
        tg = seg["girato_start"] + (tf - seg["film_start"])
        a = frame(FILM, tf, CROP["Anna"], 1)
        bs = frame(GIRATO / f"{nome}.mp4", tg - FIN / 2, CROP[nome], int(FIN * PASSO))
        if not len(a) or not len(bs):
            continue
        c, z, _ = meglio(a[0], bs)
        esiti.append(c)
        zoom.append(z)
    if not esiti:
        return {**seg, "controllo": 0.0, "zoom": None}
    return {**seg, "controllo": round(float(np.median(esiti)), 3),
            "zoom": round(float(np.median(zoom)), 2)}


if __name__ == "__main__":
    segs = json.loads((QUI / "segmenti-video.json").read_text())
    quanti = int(sys.argv[1]) if len(sys.argv) > 1 else len(segs)
    scelti = segs[:quanti]
    t0 = time.time()
    esiti = []
    for i, s in enumerate(scelti, 1):
        esiti.append(controlla(s))
        if i % 10 == 0 or i == len(scelti):
            passato = time.time() - t0
            print(f"  {i}/{len(scelti)} · {passato/i:.1f} s/segmento · "
                  f"stima totale {passato/i*len(scelti)/60:.0f} min", flush=True)
    (QUI / "controllo.json").write_text(json.dumps(esiti, indent=1))
    c = np.array([e["controllo"] for e in esiti])
    print(f"\ncontrollo su {len(c)} segmenti: mediana {np.median(c):.3f}")
    for s in (0.60, 0.70, 0.80, 0.90):
        print(f"  sopra {s:.2f}: {(c >= s).sum():4d}  ({(c >= s).mean():.0%})")
