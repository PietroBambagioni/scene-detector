"""Raggruppa gli shot in **scene**: il livello di metadati sopra il catalogo delle clip.

Metodo: *Optimal Sequential Grouping* (Rotman, Porat, Ashour — IBM 2016), programmazione dinamica
che cerca il partizionamento a blocchi **contigui** di costo intra-blocco minimo su una matrice di
distanze fra shot. Due proprietà per cui è preferito a un clustering:

- **la contiguità è nella formulazione**, non un vincolo aggiunto dopo. Il montaggio alternato
  («due o più serie di avvenimenti… in rapporto di simultaneità», *Introduzione al linguaggio del
  film* r. 1583) e il metodo di copertura (r. 1117, la stessa situazione da più angolazioni) sono
  esattamente i casi in cui un clustering per somiglianza visiva sbaglia;
- **non è addestrato**: nessun peso, nessuna dipendenza oltre numpy.

Le firme degli shot sono istogrammi HSV calcolati sui frame 48×27 che il detector legge già —
la stessa risoluzione del `ColorHistograms` interno di TransNetV2. È il segnale più povero
possibile ed è deliberato: OSG è agnostico alle feature, quindi se la misura dice che non basta si
sostituisce `shot_signatures` e il resto del file non cambia.
"""
from __future__ import annotations

import numpy as np


def shot_signatures(frames, scenes, bins=(8, 4, 4)):
    """Un istogramma HSV per shot, mediato sui suoi frame e normalizzato L1. -> (n_shot, prod(bins)).

    `frames` è l'array (n_frame, h, w, 3) RGB di `read_small_frames`.
    """
    import cv2

    nh, ns, nv = bins
    out = np.zeros((len(scenes), nh * ns * nv))
    for i, sc in enumerate(scenes):
        blk = frames[sc.start_frame:sc.end_frame + 1]  # end_frame è inclusivo
        if not len(blk):
            continue
        hsv = cv2.cvtColor(blk.reshape(-1, blk.shape[2], 3), cv2.COLOR_RGB2HSV)
        h = hsv[..., 0].astype(np.int32) * nh // 180  # OpenCV: H in 0..179
        s = hsv[..., 1].astype(np.int32) * ns // 256
        v = hsv[..., 2].astype(np.int32) * nv // 256
        out[i] = np.bincount(((h * ns + s) * nv + v).ravel(), minlength=nh * ns * nv)
    return out / np.maximum(out.sum(1, keepdims=True), 1)


SIGLIP_MODEL = "google/siglip2-base-patch16-224"


def siglip_signatures(video, scenes, n_frames=3, model=SIGLIP_MODEL, batch=32, device="mps",
                      progress=True):
    """Un embedding SigLIP per shot: media dei frame campionati, poi L2. -> (n_shot, 768).

    Stesso contratto di `shot_signatures`, feature diverse: là colore, qui semantica.

    Campiona con `sample_frames` (`captioning/caption.py`), che è già l'estrattore per-shot del
    repo — non serve una decodifica nuova. E **non** si passa da `read_small_frames`: a 224×224 un
    frame pesa 150 528 B contro i 3888 B di 48×27, cioè 38,7×, e un film di 2 h occuperebbe ~26 GB
    invece di 0,75.

    Misurato: 104 img/s su MPS (`prove/siglip_mps.py`), M-series, batch 32.
    """
    # ponytail: n_frames seek ffmpeg per shot (~20-30 min su 2000 shot). Una passata unica con
    # `select`+stride sarebbe più veloce; finché il banco mette gli embedding in cache, non paga.
    import torch
    from tqdm import tqdm
    from transformers import AutoModel, AutoProcessor

    from .captioning.caption import sample_frames

    net = AutoModel.from_pretrained(model).eval().to(device)
    proc = AutoProcessor.from_pretrained(model)

    embs, owners, imgs, pending = [], [], [], []

    def flush():
        if not imgs:
            return
        with torch.no_grad():
            px = proc(images=imgs, return_tensors="pt")["pixel_values"].to(device)
            out = net.get_image_features(pixel_values=px)
            # transformers 5.x torna un BaseModelOutputWithPooling, non un tensore
            embs.append(getattr(out, "pooler_output", out).float().cpu().numpy())
        owners.extend(pending)
        imgs.clear()
        pending.clear()

    for i, sc in enumerate(tqdm(scenes, disable=not progress, desc="[siglip] shot", unit="shot")):
        imgs.extend(sample_frames(video, sc.start_time, sc.end_time, n=n_frames, size=224,
                                  fps=sc.fps))
        pending.extend([i] * n_frames)
        if len(imgs) >= batch:
            flush()
    flush()

    return pool_by_shot(np.vstack(embs), owners, len(scenes))


def pool_by_shot(embs, owners, n_shots):
    """Media gli embedding dei frame per shot, poi L2. -> (n_shots, D).

    Fuori da `siglip_signatures` perché è l'unica parte che può sbagliare in silenzio — un
    disallineamento fra `embs` e `owners` assegna i vettori allo shot sbagliato senza esplodere —
    e così si prova senza torch né pesi.
    """
    out = np.zeros((n_shots, embs.shape[1]))
    np.add.at(out, owners, embs)
    out /= np.maximum(np.bincount(owners, minlength=n_shots), 1)[:, None]
    return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-12)


def distance_matrix(sigs):
    """1 − coseno fra le firme. Simmetrica, diagonale nulla."""
    v = sigs / np.maximum(np.linalg.norm(sigs, axis=1, keepdims=True), 1e-12)
    return np.clip(1.0 - v @ v.T, 0.0, None)


def estimate_scenes_count(D):
    """Numero di scene stimato: il "gomito" nello spettro dei valori singolari di `D`.

    `D` è simmetrica per costruzione, quindi i suoi valori singolari sono i moduli degli
    autovalori: `eigvalsh` invece di `svd`, stesso risultato e meno lavoro.

    Stima, non misura: coglie quante *apparenze distinte* ci sono, non quanti blocchi. Su
    A-B-C-A-B (5 scene, 3 palette) dice 3. `--n-scenes` è la via d'uscita, e va annotata.
    Il taglio a metà spettro impone almeno ~2 shot per scena.
    """
    sv = np.sort(np.abs(np.linalg.eigvalsh(D)))[::-1][:max(2, len(D) // 2)]
    y = np.log(sv + 1e-12)
    x = np.arange(len(y), dtype=float)
    # il gomito è il punto più lontano dalla retta che unisce il primo e l'ultimo. Cade sul primo
    # valore *trascurabile*, cioè il suo indice è già il conteggio dei significativi: niente +1.
    dx, dy = x[-1] - x[0], y[-1] - y[0]
    dist = np.abs(dx * (y - y[0]) - dy * (x - x[0])) / np.hypot(dx, dy)
    return max(1, int(np.argmax(dist)))


# Larghezza della banda: si sommano solo le coppie a distanza <= BAND shot.
#
# `H_add` così com'è nell'articolo somma **tutte** le distanze dentro un blocco, cioè pretende che
# lo shot 1 di una scena somigli al suo shot 40. Le scene vere derivano — cambia la luce, ci si
# sposta, entra un personaggio — e quel prior le spezza. La banda lo toglie e lascia solo la
# coerenza locale.
#
# Misurato su due banchi indipendenti:
#   RAI  (`prove/rai_scene_ab.py`, 116 confini) — F1@tol25 0,328 senza banda → **0,388** con W=5,
#        meglio anche di SigLIP (0,353).
#   BBC  (`prove/bbc_scene_ab.py`, 11 episodi, 4855 shot ground truth, **5 annotatori**) —
#        F1 mediana 0,242 senza banda → 0,300 con W=5 → 0,317 con W=3. McNemar appaiato senza
#        banda vs W=5: **p < 0,01 su 4 annotatori su 5**, il quinto nella stessa direzione.
#
# W=5 e non 3: 3 vince su BBC (+0,017) ma su RAI crolla al valore di "nessuna banda" (−0,060).
# 5 è ottimo su un banco e a un soffio sull'altro. La curva è unimodale su entrambi e si appiattisce
# quando W supera la scena media (~8-11 shot), che è il meccanismo atteso.
BAND = 5


def _block_costs(D, band=BAND):
    """costo[a, b] = somma delle distanze fra gli shot a..b-1 (b escluso); inf se il blocco è vuoto.

    Immagine integrale: ogni blocco costa O(1) invece di O(n²), che è ciò che rende il DP
    percorribile su 2000 shot.
    """
    n = len(D)
    if band:
        i = np.arange(n)
        D = np.where(np.abs(i[:, None] - i[None, :]) <= band, D, 0.0)
    S = np.zeros((n + 1, n + 1))
    S[1:, 1:] = D.cumsum(0).cumsum(1)
    a, b = np.arange(n + 1)[:, None], np.arange(n + 1)[None, :]
    cost = S[b, b] - S[a, b] - S[b, a] + S[a, a]
    return np.where(a < b, cost, np.inf)


def optimal_sequence(D, k, band=BAND):
    """Partiziona 0..n-1 in `k` blocchi contigui a costo H_add minimo. -> [(primo, ultimo), …] inclusivi.

    DP: `C[j, e]` = costo minimo dei primi `e` shot in `j` blocchi; `J` tiene l'inizio dell'ultimo.
    `band=0` disattiva la banda (l'H_add dell'articolo).
    """
    # ponytail: O(n²) di memoria (32 MB a 2000 shot, 800 MB a 10 000). Se un giorno morde, il DP
    # si può fare a bande sulla diagonale — una scena non abbraccia mezzo film.
    n = len(D)
    cost = _block_costs(D, band)
    C = np.full((k + 1, n + 1), np.inf)
    C[0, 0] = 0.0
    J = np.zeros((k + 1, n + 1), dtype=int)
    for j in range(1, k + 1):
        cand = C[j - 1][:, None] + cost  # cand[m, e]: taglia il blocco m..e-1
        J[j] = np.argmin(cand, axis=0)
        C[j] = cand[J[j], np.arange(n + 1)]

    groups, e = [], n
    for j in range(k, 0, -1):
        m = J[j, e]
        groups.append((int(m), e - 1))
        e = int(m)
    return groups[::-1]


def group_shots(scenes, sigs, n_scenes=None):
    """Raggruppa gli shot in scene. -> [(primo_shot, ultimo_shot), …], indici **inclusivi**.

    `sigs` è una matrice (n_shot, D) da `shot_signatures` o `siglip_signatures`: qui non si
    decodifica niente, così cambiare feature è una riga al chiamante e l'algoritmo non ha rami.

    `n_scenes=None`: il numero di scene è stimato da `estimate_scenes_count`.

    **Niente correttivo sulla punteggiatura, ed è una scelta misurata.** Il manuale
    (*Introduzione al linguaggio del film*, r. 1251) dà dissolvenza/tendina/iris come marcatori di
    blocco narrativo, e `Scene.transition` sembrava offrirli gratis. Due misure dicono di no: dei
    461 `transition` di *Rogue One* **279 sono da 2 frame**, cioè stacchi netti per costruzione
    (una corsa `i..j` diventa `(i, j+1)`); e nell'annotazione cieca i confini forzati dalle 35
    transizioni ≥6 frame — comprese una da 10 e una da 13 — sono stati giudicati **0/7 cambi di
    scena**, sotto il 15% dei controlli casuali. Il campo dice *dove* il detector ha visto una
    corsa calda, non che lì ci sia una dissolvenza. Torna quando un detector **tipizza** le
    transizioni (OmniShotCut: `Dissolve`/`Fade`/`Wipe` — VERBALE §3.8), non prima.
    """
    if len(scenes) < 2:
        return [(0, len(scenes) - 1)] if len(scenes) else []
    D = distance_matrix(sigs)
    k = max(1, min(n_scenes or estimate_scenes_count(D), len(scenes)))
    return optimal_sequence(D, k)


def build_scene_entries(groups, scenes):
    """Le voci `scenes` del manifest: indici di shot inclusivi + geometria temporale."""
    return [
        {
            "index": i,
            "first_shot": a,
            "last_shot": b,  # inclusivo, come end_frame
            "start_frame": scenes[a].start_frame,
            "end_frame": scenes[b].end_frame,
            "start_time": round(scenes[a].start_time, 3),
            "end_time": round(scenes[b].end_time, 3),
        }
        for i, (a, b) in enumerate(groups)
    ]
