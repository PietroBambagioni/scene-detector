"""Esiste sovrapposizione fra il film e il girato? — prima di cercarla bene, sapere se c'è.

L'impronta mel dava 289 segmenti che la cross-correlazione della forma d'onda ha smentito
tutti (`verifica.py`): su parlato registrato nella stessa stanza quella somiglianza non
distingue niente. Qui si prende il segnale opposto per carattere: l'**inviluppo di energia**
a 50 Hz, cioè la sagoma di pause e sillabe. Non gli importa il timbro, e due riprese diverse
della stessa conversazione hanno sagome diverse; la stessa registrazione, no.

A 50 Hz tutto il girato sta in 2,8 M campioni: un pezzo di film ci si cerca contro in un
secondo. Ogni sonda porta il suo controllo — la stessa ricerca su girato invertito nel tempo,
che ha la stessa statistica e nessuna corrispondenza possibile.

    .venv/bin/python fuoricampo/sonda.py [n_sonde]
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np

from impronta_audio import SR
from verifica import FILM, GIRATO, pcm, picco

QUI = Path(__file__).parent
HZ = 50                     # campioni di inviluppo al secondo
PASSO = SR // HZ            # 160 campioni = 20 ms
SONDA = 30.0                # secondi di film per sonda


def inviluppo(path: Path) -> np.ndarray:
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR),
         "-f", "s16le", "pipe:1"], capture_output=True).stdout
    x = np.frombuffer(out, np.int16).astype(np.float32) / 32768.0
    k = len(x) // PASSO
    rms = np.sqrt((x[:k * PASSO].reshape(k, PASSO) ** 2).mean(axis=1))
    return np.log1p(rms * 100.0).astype(np.float32)


def carica(cache=QUI / "inviluppo") -> tuple[np.ndarray, list]:
    cache.mkdir(exist_ok=True)
    fonti = [("film", FILM)] + [(f"FC{i}", GIRATO / f"Fuori campo di Anna - {i}.mp4")
                                for i in range(1, 7)]
    out = {}
    for nome, path in fonti:
        f = cache / f"{nome}.npy"
        if not f.exists():
            np.save(f, inviluppo(path))
            print(f"  {nome}: {len(np.load(f))/HZ/60:.1f} min")
        out[nome] = np.load(f)
    return out


if __name__ == "__main__":
    n_sonde = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    env = carica()
    film = env["film"]
    girato = np.concatenate([env[f"FC{i}"] for i in range(1, 7)])
    print(f"film {len(film)/HZ/60:.0f} min · girato {len(girato)/HZ/60:.0f} min · sonde da {SONDA:.0f}s")

    rng = np.random.default_rng(1)
    L = int(SONDA * HZ)
    rovescio = girato[::-1].copy()      # controllo: stessa statistica, nessun contenuto comune
    def dove_sta(t_globale, env):
        """dal tempo nel girato concatenato a (parte, secondo dentro la parte)"""
        base = 0.0
        for p in range(1, 7):
            dur = len(env[f"FC{p}"]) / HZ
            if t_globale < base + dur:
                return p, t_globale - base
            base += dur
        return 6, t_globale - base

    veri, finti, posizioni, dove_globale = [], [], [], []
    for t in np.linspace(0.02, 0.97, n_sonde):
        i = int(t * (len(film) - L))
        posizioni.append(i)
        a = film[i:i + L]
        v, dove = picco(a, girato, HZ)
        f, _ = picco(a, rovescio, HZ)
        veri.append(v)
        finti.append(f)
        dove_globale.append(dove)
        print(f"  film {i/HZ/60:6.1f} min → girato {dove/60:7.1f} min   picco {v:.3f}   controllo {f:.3f}")

    veri, finti = np.array(veri), np.array(finti)
    print(f"\npicchi:    mediana {np.median(veri):.3f}  max {veri.max():.3f}")
    print(f"controlli: mediana {np.median(finti):.3f}  max {finti.max():.3f}")
    print(f"sonde sopra il massimo dei controlli: {(veri > finti.max()).sum()}/{len(veri)}")

    # l'inviluppo propone, la forma d'onda dispone: sopra 0,30 a piena banda i due spezzoni
    # sono la stessa registrazione, sotto 0,10 non hanno niente in comune
    print("\nconferma a piena banda delle sonde migliori:")
    conf = []
    for k in np.argsort(veri)[::-1][:8]:
        i = posizioni[k]
        parte, locale = dove_sta(dove_globale[k], env)
        a = pcm(FILM, i / HZ, SONDA)
        b = pcm(GIRATO / f"Fuori campo di Anna - {parte}.mp4", locale - 5, SONDA + 10)
        v, off = picco(a, b)
        conf.append(v)
        print(f"  film {i/HZ/60:6.1f} min → FC{parte} {locale/60:6.1f} min "
              f"(inviluppo {veri[k]:.3f}) → forma d'onda {v:.3f}")
    print(f"\nverdetto: {sum(c > 0.3 for c in conf)}/{len(conf)} confermate come stessa registrazione")
