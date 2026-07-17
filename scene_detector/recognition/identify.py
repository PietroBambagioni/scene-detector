from __future__ import annotations

from collections import defaultdict

import numpy as np


def cluster_faces(embeddings, threshold=0.5, det_scores=None):
    """Clustering greedy agglomerativo su distanza coseno (embedding L2-normalizzati [N,512]).

    Un passaggio: ogni volto entra nel cluster più simile se il coseno col suo centroide è
    ≥ `threshold`, altrimenti apre un nuovo cluster. Con `det_scores` i volti più nitidi vengono
    processati per primi (seed più affidabili). Ritorna `labels[N]` (id cluster per volto,
    nell'ordine d'ingresso). Zero dip esterne — coerente con l'ethos minimale del progetto.
    """
    emb = np.asarray(embeddings, dtype=np.float64)
    n = len(emb)
    labels = np.full(n, -1, dtype=int)
    if n == 0:
        return labels
    emb = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9)
    order = np.arange(n) if det_scores is None else np.argsort(-np.asarray(det_scores))

    sums: list[np.ndarray] = []  # somma incrementale dei vettori per cluster
    counts: list[int] = []
    for idx in order:
        v = emb[idx]
        if sums:
            cents = np.stack([s / c for s, c in zip(sums, counts)])
            cents = cents / (np.linalg.norm(cents, axis=1, keepdims=True) + 1e-9)
            sims = cents @ v
            j = int(np.argmax(sims))
            if sims[j] >= threshold:
                sums[j] += v
                counts[j] += 1
                labels[idx] = j
                continue
        sums.append(v.copy())
        counts.append(1)
        labels[idx] = len(sums) - 1
    return labels


def centroids_of(embeddings, labels):
    """Centroide (normalizzato) di ogni cluster ≥ 0. -> {cluster_id: vec}."""
    emb = np.asarray(embeddings, dtype=np.float64)
    emb = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9)
    labels = np.asarray(labels)
    out = {}
    for lab in sorted({int(l) for l in labels if l >= 0}):
        m = emb[labels == lab].mean(axis=0)
        out[lab] = m / (np.linalg.norm(m) + 1e-9)
    return out


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


def build_cast(labels, shot_indices, names=None, min_faces=1):
    """Assembla il cast e i personaggi per shot da (label per volto, shot per volto).

    `names`: {cluster_id: nome reale} dalla gallery (fallback "Personaggio N"). `min_faces` scarta
    i cluster con meno volti (comparse/rumore). Ritorna:
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
        if len(sis) < min_faces:
            continue
        shots = sorted(set(sis))
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
