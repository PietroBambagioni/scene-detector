"""I segmenti trovati sono la stessa registrazione, o solo due persone che parlano?

L'impronta lavora su 32 bande mel a 4 vettori al secondo: è fatta per cercare in fretta
dentro 15 ore, non per decidere. Due brani di parlato diverso, nella stessa stanza e con lo
stesso microfono, ci correlano 0,85 senza avere nulla in comune. La prova sta a un livello
più basso: la **cross-correlazione della forma d'onda**. Se i due spezzoni sono la stessa
registrazione il picco è stretto e alto; se sono due riprese diverse non c'è picco.

Ogni segmento è misurato insieme a un controllo — lo stesso spezzone di film contro un punto
a caso del girato. Senza la distribuzione nulla il numero non dice niente.

    .venv/bin/python fuoricampo/verifica.py [n_campioni]
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from impronta_audio import SR

QUI = Path(__file__).parent
FILM = QUI.parent / "Film" / "Anna.mp4"
GIRATO = Path("/Users/pietrobambagioni/Desktop/cartella senza nome/anna film")
MARGINE = 6.0   # secondi di girato in più per lato: il picco può cadere fuori dai bordi stimati
FINESTRA = 2.0  # la finestra su cui si correla la forma d'onda, in secondi

# Perché 2 secondi e non trenta: due copie della stessa registrazione passate per catene
# diverse non hanno la stessa velocità al campione. Basta lo 0,02% di scarto — un telecine,
# un resample, un master PAL — perché su 30 s le due forme d'onda si sfasino di 6 ms e la
# correlazione crolli da 1,00 a 0,08, cioè al livello del rumore. Su 2 s lo stesso drift vale
# 0,4 ms e la correlazione regge a 0,38. Misurato: `fuoricampo/README.md`.


def pcm(path: Path, t0: float, dur: float) -> np.ndarray:
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{max(t0,0):.3f}", "-t", f"{dur:.3f}", "-i", str(path),
         "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "pipe:1"],
        capture_output=True).stdout
    return np.frombuffer(out, np.int16).astype(np.float32) / 32768.0


def picco(a: np.ndarray, b: np.ndarray, hz: float = SR) -> tuple[float, float]:
    """Massimo della cross-correlazione normalizzata di `a` dentro `b`, e dove cade (s).

    Normalizzata sull'energia locale di `b`: senza, una zona forte di `b` vince sempre.
    `hz` è l'unità di `a` e `b` — forma d'onda a 8 kHz o inviluppo a 50 Hz, la funzione non
    lo sa e la posizione va restituita nella scala giusta.
    """
    if len(a) < 8 or len(b) < len(a):
        return 0.0, 0.0
    a = a - a.mean()
    na = np.linalg.norm(a)
    if na < 1e-6:
        return 0.0, 0.0
    n = 1 << (len(b) + len(a)).bit_length()
    corr = np.fft.irfft(np.fft.rfft(b, n) * np.conj(np.fft.rfft(a, n)), n)[:len(b) - len(a) + 1]
    # energia di b su ogni finestra lunga come a, via somma cumulativa
    c2 = np.concatenate([[0.0], np.cumsum(b.astype(np.float64) ** 2)])
    en = np.sqrt(np.maximum(c2[len(a):] - c2[:-len(a)], 1e-12))[:len(corr)]
    # una finestra di silenzio ha energia ~0 al denominatore e fa esplodere il rapporto:
    # l'errore numerico dell'FFT diventa un picco da 1,7 su una correlazione che sta in [0,1]
    en = np.maximum(en, 0.1 * np.median(en))
    r = corr / (na * en)
    k = int(np.argmax(r))
    return float(r[k]), k / hz


def giudizio(film_t0: float, dur: float, parte: int, girato_t0: float) -> tuple[float, float, int]:
    """Correla finestra per finestra e guarda **dove** cadono i picchi.

    Il valore del picco da solo non basta: su 2 s di parlato una coincidenza a 0,4 non è
    rara. Quello che non capita per caso è che dieci finestre consecutive del film trovino il
    loro picco su una **retta** dentro il girato — cioè che il girato avanzi di due secondi
    ogni volta che il film avanza di due secondi. La pendenza è il drift fra le due copie, e
    la si misura invece di subirla.

    Ritorna (mediana dei picchi, frazione di finestre sulla retta, n. finestre).
    """
    dur = min(dur, 60.0)
    a = pcm(FILM, film_t0, dur)
    b = pcm(GIRATO / f"Fuori campo di Anna - {parte}.mp4",
            girato_t0 - MARGINE, dur + 2 * MARGINE)
    passo = int(FINESTRA * SR)
    n = len(a) // passo
    if n < 3 or len(b) < passo:
        return 0.0, 0.0, 0
    val, off = [], []
    for k in range(n):
        v, d = picco(a[k * passo:(k + 1) * passo], b)
        val.append(v)
        off.append(d - k * FINESTRA)      # offset girato-film: costante se è la stessa presa
    val, off = np.array(val), np.array(off)
    forti = val >= 0.25
    # sulla retta = offset entro ±0,2 s dalla mediana degli offset dei picchi forti
    if forti.sum() >= 3:
        centro = np.median(off[forti])
        allineate = (np.abs(off - centro) <= 0.2) & forti
    else:
        allineate = np.zeros(n, bool)
    return float(np.median(val)), float(allineate.mean()), n


def prova(seg: dict, rng) -> tuple[float, float]:
    dur = seg["film_end"] - seg["film_start"]
    _, vero, _ = giudizio(seg["film_start"], dur, seg["parte"], seg["girato_start"])
    _, finto, _ = giudizio(seg["film_start"], dur, seg["parte"], rng.uniform(60, 4000))
    return vero, finto


if __name__ == "__main__":
    arg = [a for a in sys.argv[1:] if not a.startswith("-")]
    k = int(arg[0]) if arg else 30
    nome = arg[1] if len(arg) > 1 else "segmenti.json"
    segs = json.loads((QUI / nome).read_text())
    rng = np.random.default_rng(0)
    scelti = [segs[i] for i in rng.choice(len(segs), min(k, len(segs)), replace=False)]

    veri, finti = [], []
    for s in scelti:
        v, f = prova(s, rng)
        veri.append(v)
        finti.append(f)
        print(f"  film {s['film_start']/60:6.1f} min → FC{s['parte']} {s['girato_start']/60:6.1f} min "
              f"({s['durata']:5.1f}s, impronta {s['score']:.2f})  allineate {v:.0%}  controllo {f:.0%}")

    veri, finti = np.array(veri), np.array(finti)
    print(f"\nfinestre allineate sui {len(veri)} segmenti: mediana {np.median(veri):.0%} · "
          f"sopra il 50%: {(veri > 0.5).sum()}/{len(veri)}")
    print(f"controlli casuali:                  mediana {np.median(finti):.0%} · "
          f"max {finti.max():.0%}")
