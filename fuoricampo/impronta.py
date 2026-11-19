"""Impronta visiva di un video: un vettore per frame campionato, confrontabile fra
sorgenti con grading e risoluzione diversi.

Il film e il girato di *Anna* sono due generazioni della stessa sorgente video b/n, con
crop, logo e contrasto diversi. La normalizzazione per frame (z-score) toglie luminosità
e contrasto; il crop centrale toglie il logo Rai in alto a sinistra e il banner
"Fuori Orario" in basso a destra, che stanno solo su una delle due.

    .venv/bin/python fuoricampo/impronta.py "Film/Anna.mp4" fuoricampo/dati
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np

FPS = 2.0    # campioni al secondo: i piani di Anna sono lunghi (media 42 s), 2/s bastano
LATO = 24    # il vettore è LATO*LATO = 576 dimensioni
GRANDE = 48  # si estrae al doppio e si scala in memoria: il film è ricadrato rispetto al
             # girato, con uno zoom che cambia da ripresa a ripresa (0,70÷0,96 misurati su
             # dieci coppie confermate), e l'unico modo di coprirlo è provare più scale.
             # Ridecodificare 19 ore per ogni scala non è un'opzione; ritagliare un 48×48
             # già in RAM costa niente.
SCALE = (0.70, 0.78, 0.86, 0.94, 1.0)

# Barre nere misurate sul 75° percentile della luminanza per colonna, su 300 frame per file:
# `cropdetect` da solo sbaglia, perché legge un frame alla volta e una scena scura ai bordi
# gli sembra barra. Non sono le stesse per tutte le parti — FC2..FC5 hanno l'immagine più
# larga di FC1 e FC6 — e usare un crop unico sposta il riquadro rispetto al film.
CROP = {
    "Anna": "1604:1080:96:0",
    "Fuori campo di Anna - 1": "1057:720:64:0",
    "Fuori campo di Anna - 2": "1151:720:64:0",
    "Fuori campo di Anna - 3": "1151:720:64:0",
    "Fuori campo di Anna - 4": "1151:720:64:0",
    "Fuori campo di Anna - 5": "1151:720:64:0",
    "Fuori campo di Anna - 6": "1044:720:64:0",
}

# Le parti che entrano nel confronto. **FC6 è fuori**: non è girato, è un rimontaggio delle
# altre. Misurato con lo stesso metodo e le stesse soglie, usando FC6 come «film»: 74 dei suoi
# 95 minuti (78%) si ritrovano in FC1..FC5. Cercandoci dentro, il montato finiva agganciato
# alla copia invece che all'originale — e il girato di quel pezzo veniva contato due volte.
# FC1 resta: non contiene un fotogramma del film (è il dibattito, vedi `etichetta` in
# timeline.py), ma il suo 0% è un risultato misurato, non un buco.
PARTI = (1, 2, 3, 4, 5)


def _cmd(path: Path, crop: str) -> list[str]:
    # fps per primo: crop e scale lavorano su 1 frame su 12 invece che su tutti.
    # 0,9 e non 0,7: il ritaglio stretto serviva a togliere logo e banner, ma butta via il
    # bordo che al girato serve per essere ristretto fino all'inquadratura del film
    vf = f"fps={FPS},crop={crop},crop=iw*0.9:ih*0.9,scale={GRANDE}:{GRANDE}"
    return [
        "ffmpeg", "-v", "error", "-i", str(path),
        "-vf", vf, "-pix_fmt", "gray", "-f", "rawvideo", "pipe:1",
    ]


def impronta(path) -> np.ndarray:
    """[N, LATO*LATO] float32, ogni riga a media 0 e norma 1: il prodotto scalare fra due
    righe è la correlazione di Pearson dei due frame."""
    path = Path(path)
    crop = CROP[path.stem]
    proc = subprocess.Popen(_cmd(path, crop), stdout=subprocess.PIPE)
    raw = proc.stdout.read()
    proc.stdout.close()
    if proc.wait() != 0:
        raise subprocess.CalledProcessError(proc.returncode, _cmd(path, crop))

    x = np.frombuffer(raw, np.uint8).reshape(-1, GRANDE, GRANDE).astype(np.float32)
    return x.astype(np.float32)   # [N, GRANDE, GRANDE] grezzo: normalizza `riduci`


def riduci(x: np.ndarray, scala: float = 1.0) -> np.ndarray:
    """Da [N, GRANDE, GRANDE] a [N, LATO*LATO] normalizzato, tenendo il `scala` centrale.

    `scala` < 1 è il girato ristretto fino a inquadrare quello che inquadra il film.
    """
    lato = max(int(round(GRANDE * scala)), LATO)
    off = (GRANDE - lato) // 2
    v = x[:, off:off + lato, off:off + lato]
    if lato != LATO:                       # media a blocchi: LATO divide 48 solo per lato=48
        idx = (np.arange(LATO) * lato // LATO)
        bordi = np.append(idx, lato)
        v = np.add.reduceat(np.add.reduceat(v, idx, axis=1), idx, axis=2)
        conteggi = np.diff(bordi).astype(np.float32)
        v = v / (conteggi[None, :, None] * conteggi[None, None, :])
    v = v.reshape(len(v), -1)
    v = v - v.mean(axis=1, keepdims=True)
    # Un frame piatto (nero, bianco) ha norma 0: correla con tutto. Lo si azzera, così il
    # prodotto scalare con qualsiasi cosa fa 0 e non entra mai in un match.
    norma = np.linalg.norm(v, axis=1, keepdims=True)
    return np.where(norma > 1e-3, v / np.maximum(norma, 1e-9), 0.0).astype(np.float32)


def smonta_gradiente(x: np.ndarray, min_residuo: float = 0.35) -> np.ndarray:
    """Toglie il gradiente lineare e azzera i frame che erano *solo* gradiente.

    Lo z-score porta a norma 1 anche un frame senza contenuto: una parete grigia con un
    filo di luce in alto diventa un vettore forte quanto un primo piano, e correla 0,93 con
    qualunque altra inquadratura chiara-sopra-scura-sotto. Il 90% dei falsi positivi era
    questo. Si proietta via il sottospazio {1, x, y} — la costante è già fuori per via dello
    z-score — e ciò che resta è la struttura vera del frame. Se resta poco (`min_residuo`
    della norma), il frame non ha di che essere riconosciuto e lo si toglie di mezzo.

    Si applica ai vettori già salvati: proiettare dopo la normalizzazione o prima cambia
    solo un fattore di scala, che la rinormalizzazione riassorbe.
    """
    g = np.mgrid[0:LATO, 0:LATO].reshape(2, -1).astype(np.float32)
    base = (g - g.mean(axis=1, keepdims=True))
    base /= np.linalg.norm(base, axis=1, keepdims=True)
    base[1] -= base[0] * (base[0] @ base[1])          # ortogonalizza y rispetto a x
    base[1] /= np.linalg.norm(base[1])

    x = x - (x @ base.T) @ base
    residuo = np.linalg.norm(x, axis=1, keepdims=True)
    return np.where(residuo >= min_residuo, x / np.maximum(residuo, 1e-9), 0.0).astype(np.float32)


def demo():
    """Due frame dello stesso video a luminosità diversa devono correlare ~1."""
    # riduci: un frame e il suo ritaglio centrale devono somigliarsi di più dopo la riduzione
    # alla scala giusta che a scala piena
    rng0 = np.random.default_rng(3)
    big = rng0.normal(size=(1, GRANDE, GRANDE)).astype(np.float32)
    big = np.cumsum(np.cumsum(big, 1), 2)          # struttura a bassa frequenza, come un'immagine
    stretto = big[:, 7:41, 7:41]                    # ~0,70 centrale, come il film sul girato
    fittizio = np.zeros((1, GRANDE, GRANDE), np.float32)
    fittizio[:] = np.repeat(np.repeat(stretto, 2, 1), 2, 2)[:, :GRANDE, :GRANDE]
    piena = (riduci(fittizio) @ riduci(big).T).item()
    giusta = (riduci(fittizio) @ riduci(big, 0.70).T).item()
    assert giusta > piena, (giusta, piena)

    a = np.arange(LATO * LATO, dtype=np.float32).reshape(1, -1)
    b = a * 0.4 + 30.0          # stesso contenuto, contrasto e offset diversi
    def norm(v):
        v = v - v.mean(axis=1, keepdims=True)
        return v / np.linalg.norm(v, axis=1, keepdims=True)
    assert abs((norm(a) @ norm(b).T).item() - 1.0) < 1e-5
    piatto = np.full((1, LATO * LATO), 128.0, np.float32)
    p = piatto - piatto.mean(axis=1, keepdims=True)
    assert np.linalg.norm(p) < 1e-3

    # due gradienti verticali diversi correlano ~1 prima, 0 dopo
    yy = np.mgrid[0:LATO, 0:LATO][0].reshape(1, -1).astype(np.float32)
    g1, g2 = norm(yy * 2.0 + 10), norm(yy * -0.7 + 3)
    assert abs((g1 @ g2.T).item()) > 0.99
    assert abs((smonta_gradiente(g1) @ smonta_gradiente(g2).T).item()) < 1e-3
    # un frame con struttura vera sopravvive e resta uguale a se stesso
    rng = np.random.default_rng(0)
    v = norm(rng.normal(size=(1, LATO * LATO)).astype(np.float32) * 40 + yy)
    assert (smonta_gradiente(v) @ smonta_gradiente(v).T).item() > 0.99
    print("ok")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--demo"]:
        demo()
        raise SystemExit

    src, outdir = Path(sys.argv[1]), Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / (src.stem.replace(" ", "_") + ".npy")
    x = impronta(src)
    np.save(out, x.astype(np.uint8))
    print(f"{out}  {x.shape}  {x.nbytes/1e6:.0f} MB  {len(x)/FPS/60:.1f} min")
