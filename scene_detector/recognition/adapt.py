from __future__ import annotations

import numpy as np

# Iperparametri di VGG Oxford (arXiv 2509.12204), che aggiorna il solo ultimo layer lineare di
# DINOv2 in contrastivo. Qui l'encoder resta congelato e si addestra una testa lineare sugli
# embedding gia' calcolati: secondi, non ore, e nessuna GPU esterna.
DIM, TAU, STEPS, LR0, LR1 = 256, 0.07, 400, 6e-4, 5e-6


def train_adapter(embeddings, ids, dim=DIM, steps=STEPS, tau=TAU, device="mps", seed=0):
    """Testa lineare contrastiva sulle identita' *maestre*. -> matrice W [dim, d].

    `ids[N]`: identita' per embedding, `-1` per chi non insegna. I positivi sono le coppie con
    lo stesso id, i negativi quelle con id diverso.

    **Da dove viene la supervisione, e perche' non da altrove.** Servono positivi *cross-shot*:
    l'invarianza che conta e' quella a luce, posa, scala e sfondo, e dentro un solo shot quella
    variazione non c'e'. Misurato su *Rogue One*: usando «stesso shot = stessa identita'» si
    ottengono 8 191 positivi dichiarati contro **2 676 785** coppie della stessa identita'
    finite fra i negativi — la testa impara l'identita' dello *shot* e frammenta tutto
    (240 ritagli di due protagonisti -> 71 gruppi). Vale anche per le tracce: **una traccia non
    attraversa uno stacco**.

    La fonte che funziona senza dati esterni sono i cluster ArcFace **affidabili** del film
    stesso (`faces.teacher_clusters`): sui volti umani scoperti ArcFace lega correttamente
    attraverso gli stacchi, e cio' che varia fra uno shot e l'altro e' proprieta' della
    fotografia del film, non del personaggio. Imparata li', si applica anche ai non-umani.

    SupCon e non InfoNCE a coppie: con le coppie, gli altri membri della stessa identita'
    finiscono fra i negativi l'uno dell'altro.
    """
    import torch

    ids = np.asarray(ids)
    m = np.flatnonzero(ids >= 0)
    if len(m) < 2 or len(set(ids[m].tolist())) < 2:
        return None

    torch.manual_seed(seed)
    if device == "mps" and not torch.backends.mps.is_available():
        device = "cpu"
    X = torch.from_numpy(np.asarray(embeddings, np.float32)[m]).to(device)
    Y = torch.from_numpy(ids[m]).to(device)

    W = torch.nn.Linear(X.shape[1], dim, bias=False).to(device)
    opt = torch.optim.AdamW(W.parameters(), lr=LR0)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps, eta_min=LR1)
    eye = torch.eye(len(m), dtype=torch.bool, device=device)
    pos = (Y[:, None] == Y[None, :]) & ~eye
    if not bool(pos.any()):
        return None

    for _ in range(steps):
        z = torch.nn.functional.normalize(W(X), dim=1)
        sim = ((z @ z.T) / tau).masked_fill(eye, -1e4)
        logp = (sim - torch.logsumexp(sim, 1, keepdim=True)).masked_fill(~pos, 0.0)
        loss = -(logp.sum(1) / pos.sum(1).clamp(min=1)).mean()
        opt.zero_grad()
        loss.backward()
        opt.step()
        sched.step()

    return W.weight.detach().cpu().numpy()


def project(embeddings, W):
    """Proietta con la testa addestrata e rinormalizza. -> [N, dim]."""
    z = np.asarray(embeddings, np.float32) @ np.asarray(W, np.float32).T
    return z / (np.linalg.norm(z, axis=1, keepdims=True) + 1e-9)
