"""Impronta audio: stessa griglia e stesso contratto di `impronta.py`, altro segnale.

Il video, su questo materiale, è il caso peggiore: bianco e nero, sempre la stessa stanza,
crop diverso in ogni parte del girato, e un fondo di frame grigi che correlano con tutto.
L'audio è il caso migliore — *Anna* è in presa diretta, quindi un pezzo di girato finito nel
film porta con sé la stessa voce, sulla stessa stanza, con lo stesso riverbero, e niente di
tutto ciò dipende da come è stato ritagliato il fotogramma.

Un vettore ogni 0,5 s (FPS=2, la griglia di `impronta.py`), che descrive una finestra di 2 s:
32 bande mel × 8 istanti. Normalizzato a media 0 e norma 1, come il video: `match.py` non sa
e non deve sapere da quale dei due segnali arrivano i vettori che confronta.

    .venv/bin/python fuoricampo/impronta_audio.py "Film/Anna.mp4" fuoricampo/audio
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np

from impronta import FPS

SR = 8000        # il parlato sta tutto sotto i 4 kHz e il decode dimezza
NFFT, HOP = 1024, 500   # 500 su 8 kHz = 16 frame/s esatti: la griglia deve cadere
                        # su 1/FPS senza resto, o l'indice deriva di minuti su un film intero
BANDE = 32
FINESTRA = 2.0   # secondi descritti da ogni vettore
SLOT = 8         # istanti per finestra: 0,25 s l'uno
CODA = FINESTRA - 1 / FPS   # il vettore i copre [i/FPS, i/FPS + FINESTRA]: la coda va aggiunta
                            # alla fine di un segmento, che altrimenti risulta corto di 1,5 s
MIN_ENERGIA = 0.25   # frazione dell'energia mediana sotto cui il silenzio non è riconoscibile
ENERGIA_ASSOLUTA = 0.02   # e comunque mai sotto questa: un file tutto silenzio ha mediana zero


def _mel(n_freq: int) -> np.ndarray:
    """Banco triangolare mel fra 100 e 3800 Hz, righe a somma 1."""
    m = lambda f: 2595 * np.log10(1 + f / 700)
    inv = lambda x: 700 * (10 ** (x / 2595) - 1)
    punti = inv(np.linspace(m(100), m(3800), BANDE + 2))
    freq = np.linspace(0, SR / 2, n_freq)
    b = np.zeros((BANDE, n_freq), np.float32)
    for i in range(BANDE):
        sx, c, dx = punti[i:i + 3]
        b[i] = np.clip(np.minimum((freq - sx) / (c - sx), (dx - freq) / (dx - c)), 0, None)
    return b / np.maximum(b.sum(axis=1, keepdims=True), 1e-9)


def _pcm(path: Path) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR),
           "-f", "s16le", "pipe:1"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    raw = proc.stdout.read()
    proc.stdout.close()
    if proc.wait() != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def impronta(path) -> np.ndarray:
    return vettori(_pcm(Path(path)))


def vettori(x: np.ndarray) -> np.ndarray:
    n = 1 + (len(x) - NFFT) // HOP
    if n <= 0:
        return np.zeros((0, BANDE * SLOT), np.float32)
    frames = np.lib.stride_tricks.as_strided(
        x, (n, NFFT), (x.strides[0] * HOP, x.strides[0]), writeable=False)
    finestra = np.hanning(NFFT).astype(np.float32)
    banco = _mel(NFFT // 2 + 1)
    # a blocchi: l'FFT di 3 ore d'audio in un colpo sono 2 GB di picco per niente,
    # il mel che ne esce sta in 25 MB
    mel = np.empty((n, BANDE), np.float32)
    for a in range(0, n, 20000):
        spec = np.abs(np.fft.rfft(frames[a:a + 20000] * finestra, axis=1))
        mel[a:a + 20000] = np.log1p(spec @ banco.T * 100.0)

    # da 15,6 frame/s a SLOT istanti per finestra: la media su 4 frame assorbe i piccoli
    # disallineamenti fra le due copie senza spegnere il contenuto
    per_slot = max(int(round(SR / HOP * FINESTRA / SLOT)), 1)
    k = len(mel) // per_slot
    grossi = mel[:k * per_slot].reshape(k, per_slot, BANDE).mean(axis=1)   # 1 riga ogni 0,25 s

    # `grossi` avanza di FINESTRA/SLOT secondi per riga: quante righe fanno 1/FPS secondi
    passo = max(int(round((1 / FPS) / (FINESTRA / SLOT))), 1)
    n_vec = (len(grossi) - SLOT) // passo + 1
    if n_vec <= 0:
        return np.zeros((0, BANDE * SLOT), np.float32)
    v = np.lib.stride_tricks.as_strided(
        grossi, (n_vec, SLOT, BANDE),
        (grossi.strides[0] * passo, grossi.strides[0], grossi.strides[1]),
        writeable=False).reshape(n_vec, SLOT * BANDE).copy()

    # il silenzio è l'attrattore dell'audio come il grigio piatto lo è del video: una finestra
    # senza energia correla con qualunque altra finestra senza energia
    energia = v.mean(axis=1)
    sonore = energia[energia > 0]
    soglia = max(ENERGIA_ASSOLUTA, MIN_ENERGIA * (np.median(sonore) if len(sonore) else 0.0))
    vivo = energia >= soglia

    v -= v.mean(axis=1, keepdims=True)
    norma = np.linalg.norm(v, axis=1, keepdims=True)
    v = np.where((norma > 1e-6) & vivo[:, None], v / np.maximum(norma, 1e-9), 0.0)
    return v.astype(np.float32)


def demo():
    """Lo stesso audio a volume diverso e con un filo di rumore resta riconoscibile;
    due silenzi no."""
    rng = np.random.default_rng(0)
    t = np.arange(SR * 12) / SR
    voce = (np.sin(2 * np.pi * 300 * t) * (1 + np.sin(2 * np.pi * 3 * t))
            + 0.5 * np.sin(2 * np.pi * 900 * t * (1 + 0.1 * np.sin(2 * np.pi * t))))

    a = vettori(voce.astype(np.float32))
    b = vettori((voce * 0.3 + rng.normal(scale=0.01, size=len(voce))).astype(np.float32))
    assert len(a) == len(b) > 10, (len(a), len(b))
    corr = float((a * b).sum(axis=1)[5])
    assert corr > 0.9, corr
    silenzio = vettori(rng.normal(scale=1e-5, size=len(voce)).astype(np.float32))
    assert np.abs(silenzio).sum() == 0.0, "il silenzio deve essere azzerato"
    print(f"ok (corr {corr:.3f})")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--demo"]:
        demo()
        raise SystemExit
    src, outdir = Path(sys.argv[1]), Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / (src.stem.replace(" ", "_") + ".npy")
    v = impronta(src)
    np.save(out, v)
    vivi = (np.abs(v).sum(axis=1) > 0).mean()
    print(f"{out}  {v.shape}  {len(v)/FPS/60:.1f} min  · {vivi:.0%} finestre con suono")
