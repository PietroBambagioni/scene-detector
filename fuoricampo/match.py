"""Trova nel girato i pezzi finiti nel film montato.

Non basta la somiglianza fra due frame: il materiale è tutto in bianco e nero, nella stessa
stanza, con le stesse persone, e piani lunghi. Un frame del film somiglia a mezz'ora di
girato. Quello che distingue un riuso vero da una coincidenza è la **coerenza temporale**:
per venti secondi di fila il girato avanza di un frame ogni volta che avanza il film, cioè
l'offset `idx_girato - idx_film` resta costante. È questo che si cerca — la soglia sul
singolo frame serve solo a scartare il rumore prima del voting.

    .venv/bin/python fuoricampo/match.py            # -> segmenti.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch

from impronta import FPS, PARTI, SCALE, riduci, smonta_gradiente
from timeline import REGISTRO, annota_passo
import impronta_audio

QUI = Path(__file__).parent

TOPK = 5          # candidati per frame: il miglior match può cadere su un altro ciak
TH_FRAME = 0.70   # correlazione minima perché un candidato entri nel voting
TH_SEG = 0.80     # correlazione mediana minima del segmento accettato
TOL = 2           # scarto ammesso sull'offset, in campioni (±1 s)
MAX_GAP = 6       # buco tollerato dentro un segmento, in campioni (3 s)
MIN_LEN = 6       # durata minima del segmento, in campioni (3 s)
MIN_MOTO = 0.012  # quanto il film deve cambiare da un campione al successivo, dentro il
                  # segmento. Su un'immagine ferma la coerenza temporale non dimostra niente:
                  # una corsa di sei fotogrammi identici «avanza in parallelo» a qualunque
                  # altra corsa di sei fotogrammi identici, e il voting approva senza aver
                  # verificato nulla. È così che il cartello «si consiglia la visione a un
                  # pubblico adulto» finiva agganciato a una targa incisa nel girato: a 24×24
                  # sono entrambi un rettangolo chiaro su fondo scuro, e nessuno dei due si
                  # muove. Misurati: cartelli e titoli di coda 0,000÷0,003, inquadrature vere
                  # 0,018÷0,318.
MIN_CONTRASTO = 15.0  # e nemmeno il **buio** si può verificare: un fotogramma quasi nero
                  # accoppia con qualunque cosa, e `MIN_MOTO` non lo ferma perché la grana si
                  # muove eccome. Misurati sui falsi trovati riverificando a piena risoluzione:
                  # i due col fotogramma vuoto stanno a 12,5 e 13,4 di deviazione standard,
                  # i veri confermati fra 48 e 71, e il primo percentile dei segmenti è 16,8.


def carica_girato(dati: Path, video: bool):
    """Le parti concatenate in un unico array, più la mappa per tornare a (parte, secondo)."""
    blocchi, inizi = [], []
    for i in PARTI:
        x = np.load(dati / f"Fuori_campo_di_Anna_-_{i}.npy")
        inizi.append(sum(len(b) for b in blocchi))
        blocchi.append(x)
    lunghezze = [len(b) for b in blocchi]
    if not video:
        return [np.concatenate(blocchi)], np.array(inizi), lunghezze
    # una versione del girato per ogni scala: il film ne inquadra una porzione variabile
    return ([np.concatenate([smonta_gradiente(riduci(b.astype(np.float32), z)) for b in blocchi])
             for z in SCALE], np.array(inizi), lunghezze)


def base_di(parte: int, inizi) -> int:
    """Dove comincia una parte dentro il girato concatenato.

    Per **numero di parte**, non per `parte - 1`: le parti in gioco sono `PARTI` e non
    l'intervallo 1..6, quindi la posizione nella concatenazione non è il numero meno uno.
    """
    return int(inizi[PARTI.index(parte)])


def candidati(film, versioni, device):
    """Per ogni frame del film i TOPK frame di girato più correlati, su tutte le scale.

    Il prodotto scalare fra righe normalizzate è la correlazione: un matmul a blocchi per
    scala. Le scale si confrontano una alla volta e si tiene il meglio, invece di
    concatenarle: la GPU regge 250 MB per volta senza dover ospitare tutto il girato ×5.
    """
    F = torch.from_numpy(film).to(device)
    idx = np.zeros((len(film), 0), np.int64)
    val = np.zeros((len(film), 0), np.float32)
    sca = np.zeros((len(film), 0), np.int8)
    for k, g in enumerate(versioni):
        G = torch.from_numpy(g).to(device).T.contiguous()
        vi, vv = [], []
        for a in range(0, len(F), 512):
            v, i = torch.topk(F[a:a + 512] @ G, TOPK, dim=1)
            vv.append(v.cpu().numpy())
            vi.append(i.cpu().numpy())
        del G
        idx = np.hstack([idx, np.concatenate(vi)])
        val = np.hstack([val, np.concatenate(vv)])
        sca = np.hstack([sca, np.full((len(film), TOPK), k, np.int8)])
    # dei TOPK×len(SCALE) candidati raccolti si tengono i TOPK migliori complessivi
    ordine = np.argsort(-val, axis=1)[:, :TOPK]
    r = np.arange(len(film))[:, None]
    return idx[r, ordine], val[r, ordine], sca[r, ordine]


def moto_film(F: np.ndarray) -> np.ndarray:
    """Quanto ogni campione del film differisce dal successivo: 0 = immagine ferma."""
    m = np.zeros(len(F), np.float32)
    m[:-1] = 1.0 - (F[:-1] * F[1:]).sum(axis=1)
    return m


def contrasto_film(grezzo: np.ndarray) -> np.ndarray:
    """Deviazione standard dei pixel, sui dati **prima** della normalizzazione.

    Va misurata sul grezzo: lo z-score porta a norma 1 anche un fotogramma nero, ed è proprio
    quella l'informazione che serve qui.
    """
    return grezzo.reshape(len(grezzo), -1).astype(np.float32).std(axis=1)


def segmenti(idx, val, file_di, moto=None, contrasto=None):
    """Corse di frame del film che avanzano in parallelo al girato, a offset costante.

    Greedy: parte dal primo frame sopra soglia, prova i suoi candidati, e per ciascuno vede
    fin dove la diagonale regge. Il primo che arriva a MIN_LEN vince e il cursore salta oltre.
    """
    n = len(idx)
    out, i = [], 0
    while i < n:
        if val[i, 0] < TH_FRAME:
            i += 1
            continue
        migliore = None
        for c in range(TOPK):
            if val[i, c] < TH_FRAME:
                break
            off = int(idx[i, c]) - i
            corsa = [(i, int(idx[i, c]), float(val[i, c]))]
            j, gap = i + 1, 0
            while j < n and gap <= MAX_GAP:
                atteso = j + off
                scelto = None
                for c2 in range(TOPK):
                    if val[j, c2] < TH_FRAME:
                        break
                    if abs(int(idx[j, c2]) - atteso) <= TOL and file_di[idx[j, c2]] == file_di[corsa[0][1]]:
                        scelto = (int(idx[j, c2]), float(val[j, c2]))
                        break
                if scelto:
                    corsa.append((j, scelto[0], scelto[1]))
                    off = scelto[0] - j   # segue la deriva lenta fra le due sorgenti
                    gap = 0
                else:
                    gap += 1
                j += 1
            if len(corsa) >= MIN_LEN and (migliore is None or len(corsa) > len(migliore)):
                migliore = corsa
        # un segmento vale solo se il film, lì dentro, è **verificabile**: si muove e si vede
        inverificabile = False
        if migliore is not None:
            dove = [c[0] for c in migliore]
            inverificabile = (
                (moto is not None and float(np.median(moto[dove])) < MIN_MOTO)
                or (contrasto is not None
                    and float(np.median(contrasto[dove])) < MIN_CONTRASTO))
        if migliore and not inverificabile and float(np.median([c[2] for c in migliore])) >= TH_SEG:
            out.append(migliore)
            i = migliore[-1][0] + 1
        else:
            i += 1
    return out


def demo():
    """Una diagonale piantata nel rumore va trovata; il rumore da solo no."""
    rng = np.random.default_rng(0)
    n, m = 200, 400
    idx = rng.integers(0, m, size=(n, TOPK))
    val = np.full((n, TOPK), 0.3, np.float32)
    for k, i in enumerate(range(50, 70)):          # 20 campioni a offset 100
        idx[i, 0], val[i, 0] = 100 + i, 0.95
    file_di = np.zeros(m, int)
    segs = segmenti(idx, val, file_di)
    assert len(segs) == 1, segs
    assert segs[0][0][0] == 50 and segs[0][-1][0] == 69, segs[0]
    assert segmenti(rng.integers(0, m, (n, TOPK)), np.full((n, TOPK), 0.3, np.float32), file_di) == []
    # la stessa diagonale, ma su un film fermo: non è più una prova di niente
    fermo = np.full(n, 0.001, np.float32)
    vivo = np.full(n, 0.2, np.float32)
    assert segmenti(idx, val, file_di, fermo) == []
    assert len(segmenti(idx, val, file_di, vivo)) == 1
    # la stessa diagonale su un film al buio: non è più una prova di niente
    assert segmenti(idx, val, file_di, vivo, np.full(n, 5.0, np.float32)) == []
    assert len(segmenti(idx, val, file_di, vivo, np.full(n, 50.0, np.float32))) == 1
    print("ok")


if __name__ == "__main__":
    import sys
    if "--demo" in sys.argv:
        demo()
        raise SystemExit

    video = "--video" in sys.argv
    dati = QUI / ("dati" if video else "audio")
    coda = 0.0 if video else impronta_audio.CODA
    film = np.load(dati / "Anna.npy")
    contrasto = contrasto_film(film) if video else None
    if video:
        film = smonta_gradiente(riduci(film.astype(np.float32)))
    versioni, inizi, lunghezze = carica_girato(dati, video)
    file_di = np.concatenate([np.full(l, p) for p, l in zip(PARTI, lunghezze)])

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"film {film.shape} · girato {versioni[0].shape} × {len(versioni)} scale · {device}")
    idx, val, sca = candidati(film, versioni, device)
    np.savez(QUI / "candidati.npz", idx=idx, val=val, sca=sca, file_di=file_di, inizi=inizi,
             moto=moto_film(film) if video else np.zeros(len(film), np.float32),
             contrasto=contrasto if video else np.zeros(len(film), np.float32))
    print(f"correlazione del miglior candidato: mediana {np.median(val[:,0]):.3f} · "
          f"sopra {TH_FRAME}: {(val[:,0] >= TH_FRAME).mean():.1%} dei frame")

    segs = segmenti(idx, val, file_di,
                    moto_film(film) if video else None,
                    contrasto if video else None)
    res = []
    for s in segs:
        g0, g1 = s[0][1], s[-1][1]
        parte = int(file_di[g0])
        base = base_di(parte, inizi)
        res.append({
            "film_start": s[0][0] / FPS, "film_end": (s[-1][0] + 1) / FPS + coda,
            "parte": parte,
            "girato_start": (g0 - base) / FPS, "girato_end": (g1 - base + 1) / FPS + coda,
            "durata": (s[-1][0] + 1 - s[0][0]) / FPS + coda,
            "score": round(float(np.median([c[2] for c in s])), 3),
            "n": len(s),
        })
    (QUI / ("segmenti-video.json" if video else "segmenti.json")).write_text(json.dumps(res, indent=1))
    if video:
        REGISTRO.unlink(missing_ok=True)   # un match nuovo azzera i passi che lo seguivano
        annota_passo("match", res, parti=list(PARTI),
                     soglie={"TH_FRAME": TH_FRAME, "TH_SEG": TH_SEG, "MIN_LEN": MIN_LEN})
    tot = sum(r["durata"] for r in res)
    print(f"{len(res)} segmenti · {tot/60:.1f} min di film ritrovati nel girato "
          f"({tot/(len(film)/FPS):.1%} del film)")
