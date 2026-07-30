from __future__ import annotations

from collections import defaultdict

import numpy as np


def cluster_faces(embeddings, threshold=0.5, det_scores=None, frame_indices=None):
    """Clustering greedy agglomerativo su distanza coseno (embedding L2-normalizzati [N,512]).

    Un passaggio: ogni volto entra nel cluster più simile se il coseno col suo centroide è
    ≥ `threshold`, altrimenti apre un nuovo cluster. Con `det_scores` i volti più nitidi vengono
    processati per primi (seed più affidabili). Ritorna `labels[N]` (id cluster per volto,
    nell'ordine d'ingresso). Zero dip esterne — coerente con l'ethos minimale del progetto.

    Con `frame_indices` vale il vincolo *must-not-link*: un volto non può entrare in un cluster
    che contiene già un volto dello **stesso frame**, perché due facce compresenti sono due
    persone per quanto si somiglino. È il vincolo che impedisce a un campo/controcampo di
    collassare in un'identità sola, e serve allo stadio 1 di `cluster_two_stage`.
    """
    emb = np.asarray(embeddings, dtype=np.float64)
    n = len(emb)
    labels = np.full(n, -1, dtype=int)
    if n == 0:
        return labels
    emb = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9)
    frames = None if frame_indices is None else [int(f) for f in frame_indices]
    order = np.arange(n) if det_scores is None else np.argsort(-np.asarray(det_scores))

    sums: list[np.ndarray] = []  # somma incrementale dei vettori per cluster
    counts: list[int] = []
    seen: list[set] = []         # seen[j] = frame gia' rappresentati nel cluster j
    for idx in order:
        v = emb[idx]
        if sums:
            cents = np.stack([s / c for s, c in zip(sums, counts)])
            cents = cents / (np.linalg.norm(cents, axis=1, keepdims=True) + 1e-9)
            sims = cents @ v
            if frames is not None:
                sims = np.where([frames[idx] in s for s in seen], -np.inf, sims)
            j = int(np.argmax(sims))
            if sims[j] >= threshold:
                sums[j] += v
                counts[j] += 1
                labels[idx] = j
                if frames is not None:
                    seen[j].add(frames[idx])
                continue
        sums.append(v.copy())
        counts.append(1)
        seen.append({frames[idx]} if frames is not None else set())
        labels[idx] = len(sums) - 1
    return labels


# ------------------------------------------------- clustering a due stadi (4.4) ---
# Clusterizzare i singoli volti dell'intero film spezza una persona in piu' identita': su Anna
# 1634 volti -> 68 cluster per una decina di presenze reali. La cura canonica e' clusterizzare
# le *tracce* invece dei frame, ma le tracce presuppongono video denso: noi campioniamo 6 frame
# sparsi per shot via seek, e fra un campione e l'altro un volto attraversa l'inquadratura —
# IoU e Kalman (ByteTrack) non hanno appiglio. L'equivalente che regge con frame sparsi e'
# raggruppare *dentro lo shot* per somiglianza, con il vincolo must-not-link per frame.


def average_embeddings(embeddings, labels):
    """Un embedding mediato e normalizzato per gruppo. -> (emb[K,512], group_ids[K], sizes[K]).

    E' il passaggio che rende il secondo stadio robusto: la media di piu' viste dello stesso
    volto cancella il rumore di posa e messa a fuoco che fa deragliare il singolo frame.
    """
    emb = np.asarray(embeddings, dtype=np.float64)
    emb = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9)
    labels = np.asarray(labels)
    ids = sorted({int(l) for l in labels if l >= 0})
    if not ids:
        return np.zeros((0, emb.shape[1] if emb.ndim > 1 else 0)), [], []
    means, sizes = [], []
    for lab in ids:
        m = emb[labels == lab].mean(axis=0)
        means.append(m / (np.linalg.norm(m) + 1e-9))
        sizes.append(int((labels == lab).sum()))
    return np.stack(means), ids, sizes


def cluster_two_stage(embeddings, shot_indices, frame_indices, threshold=0.5, det_scores=None):
    """Clustering a due stadi: dentro lo shot, poi sui gruppi mediati. -> `labels[N]` per volto.

    Stadio 1: `cluster_faces` per ogni shot con `frame_indices` (vincolo must-not-link).
    Stadio 2: `cluster_faces` sugli embedding **mediati** dei gruppi, ordinati per numerosita' —
    i gruppi grandi fanno da seed, che e' piu' affidabile del singolo volto piu' nitido.
    L'interfaccia resta quella di `cluster_faces`: un'etichetta per volto in ingresso, quindi
    `build_cast` e la gallery non cambiano.
    """
    emb = np.asarray(embeddings, dtype=np.float64)
    n = len(emb)
    if n == 0:
        return np.full(0, -1, dtype=int)
    shots = [int(s) for s in shot_indices]
    scores = None if det_scores is None else np.asarray(det_scores)

    # stadio 1 — etichette di gruppo globalmente uniche (shot, label locale)
    group_of = np.full(n, -1, dtype=int)
    n_groups = 0
    for shot in sorted(set(shots)):
        idx = [i for i, s in enumerate(shots) if s == shot]
        local = cluster_faces(emb[idx], threshold, None if scores is None else scores[idx],
                              frame_indices=[frame_indices[i] for i in idx])
        for i, lab in zip(idx, local):
            group_of[i] = n_groups + int(lab)
        n_groups += int(local.max()) + 1 if len(local) else 0

    # stadio 2 — un vettore per gruppo, clusterizzati fra loro
    means, ids, sizes = average_embeddings(emb, group_of)
    group_labels = cluster_faces(means, threshold, det_scores=sizes)
    to_final = {g: int(l) for g, l in zip(ids, group_labels)}
    return np.array([to_final.get(int(g), -1) for g in group_of], dtype=int)


def refine_clusters(labels, embeddings, targets, threshold=0.5, min_size=5):
    """Ri-clusterizza i soli cluster in `targets` in uno spazio diverso. -> (labels, spezzati).

    Serve dove ArcFace non e' un rilevatore di identita' ma di volti umani: sui droidi e sugli
    elmetti i suoi vettori descrivono «oggetto scuro a forma di testa», e il risultato e' un
    cluster che ne fonde diversi (su *Rogue One*: 259 volti in 93 shot fra K-2SO, Darth Vader,
    gli stormtrooper, un pilota con la visiera e una creatura pelosa).

    **Conservativo per costruzione.** Il gruppo piu' numeroso tiene l'id originale, e solo i
    gruppi da almeno `min_size` membri ne ricevono uno nuovo: chi finisce in un gruppetto resta
    dov'era. Se il cluster non si separa in almeno due gruppi significativi si lascia **intatto**
    — meglio un cluster fuso noto che una frammentazione inventata.

    Nota storica: l'ibrido «ArcFace primario + ri-clustering di apparenza» era stato provato con
    SigLIP grezzo e scartato (`plan/DA-FARE.md` §2), perche' produceva
    `{stormtrooper+Vader}, {K-2SO chiaro}, {K-2SO scuro}` — spaccava K-2SO **per illuminazione**.
    Il motivo era l'encoder, non lo schema: con gli embedding adattati (`adapt.train_adapter`)
    K-2SO resta un gruppo solo attraverso illuminazioni molto diverse.
    """
    labels = np.asarray(labels).copy()
    if not len(labels):
        return labels, set()
    nxt = int(labels.max()) + 1
    spezzati = set()

    for c in sorted(int(t) for t in targets):
        m = np.flatnonzero(labels == c)
        if len(m) < 2 * min_size:
            continue
        sub = cluster_faces(embeddings[m], threshold)
        sizes = np.bincount(sub[sub >= 0])
        big = [g for g in range(len(sizes)) if sizes[g] >= min_size]
        if len(big) < 2:
            continue
        big.sort(key=lambda g: -sizes[g])
        for g in big[1:]:                    # il piu' grande tiene l'id, gli altri si staccano
            labels[m[sub == g]] = nxt
            spezzati.add(nxt)
            nxt += 1
        spezzati.add(c)

    return labels, spezzati


def centroids_of(embeddings, labels):
    """Centroide (normalizzato) di ogni cluster ≥ 0. -> {cluster_id: vec}."""
    means, ids, _ = average_embeddings(embeddings, labels)
    return dict(zip(ids, means))


def match_gallery(centroids, gallery, threshold=0.5):
    """Mappa i centroidi dei cluster ai nomi della gallery per coseno (matching 1-a-1 greedy).

    `centroids`: {cluster_id: vec}; `gallery`: {nome: vec}. Si accoppiano le coppie a similarità
    decrescente ≥ `threshold`, senza riusare lo stesso nome né lo stesso cluster.
    -> {cluster_id: nome} (solo i cluster con un match).
    """
    if not gallery or not centroids:
        return {}
    names = list(gallery)
    G = np.stack([gallery[nm] / (np.linalg.norm(gallery[nm]) + 1e-9) for nm in names])

    flat = []  # (sim, cluster_id, nome)
    for cid, v in centroids.items():
        vv = v / (np.linalg.norm(v) + 1e-9)
        for k, sim in enumerate(G @ vv):
            flat.append((float(sim), cid, names[k]))
    flat.sort(reverse=True)

    assigned, used = {}, set()
    for sim, cid, nm in flat:
        if sim < threshold:
            break
        if cid in assigned or nm in used:
            continue
        assigned[cid] = nm
        used.add(nm)
    return assigned


def build_cast(labels, shot_indices, names=None, min_shots=2):
    """Assembla il cast e i personaggi per shot da (label per volto, shot per volto).

    `names`: {cluster_id: nome reale} dalla gallery (fallback "Personaggio N"). `min_shots` scarta
    i cluster visti in meno di N **shot distinti** — non in meno di N *volti*: un personaggio del
    cast e' chi *ricorre fra gli shot*, mentre lo stesso volto in due frame di un solo shot resta
    un'apparizione unica. Misurato su Rogue One (8839 volti): il taglio per volti a >=2 lascia 274
    "personaggi", quello per shot a >=2 ne lascia 113, tagliando netto i 548 apparsi una volta.
    Ritorna:
      - `cast`: lista di {id, name, n_faces, n_shots, shots}, ordinata per n_shots desc.
      - `per_shot`: {shot_index: set(cluster_id)} limitato ai cluster tenuti nel cast.
    """
    names = names or {}
    labels = [int(l) for l in labels]
    faces_per = defaultdict(list)  # cluster -> lista shot (con ripetizioni = n volti)
    for lab, si in zip(labels, shot_indices):
        if lab >= 0:
            faces_per[lab].append(int(si))

    cast = []
    for cid, sis in faces_per.items():
        shots = sorted(set(sis))
        if len(shots) < min_shots:
            continue
        cast.append({
            "id": cid,
            "name": names.get(cid) or f"Personaggio {cid + 1}",
            "n_faces": len(sis),
            "n_shots": len(shots),
            "shots": shots,
        })
    cast.sort(key=lambda c: (-c["n_shots"], c["id"]))

    kept = {c["id"] for c in cast}
    per_shot = defaultdict(set)
    for lab, si in zip(labels, shot_indices):
        if lab in kept:
            per_shot[int(si)].add(lab)
    return cast, per_shot
