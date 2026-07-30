from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .identify import build_cast, centroids_of, cluster_two_stage, match_gallery


@dataclass
class DetectedFace:
    shot_index: int
    frame_index: int       # quale dei frame campionati dello shot (serve al must-not-link)
    embedding: np.ndarray  # ArcFace normed 512
    det_score: float
    thumb: object          # PIL.Image — crop del volto (per la card del cast)


class FaceRecognizer:
    """Backend InsightFace: SCRFD (detection) + ArcFace (embedding), pacchetto `buffalo_l`.

    Gira su CoreML (Apple Silicon) con fallback CPU. Import di insightface differito al costruttore
    così il modulo resta importabile senza l'extra `faces`.
    """

    def __init__(self, model_name="buffalo_l", det_size=640, min_score=0.5, providers=None):
        import warnings

        from insightface.app import FaceAnalysis

        # insightface chiama `SimilarityTransform.estimate`, deprecata in scikit-image: emette un
        # FutureWarning **a ogni volto** (migliaia per film) che spezza la progress bar tqdm e
        # sommerge il log. È codice di terze parti, non nostro. Zittito solo questo, per messaggio.
        warnings.filterwarnings("ignore", message=".*estimate.*is deprecated.*",
                                category=FutureWarning)

        self.min_score = min_score
        self.app = FaceAnalysis(
            name=model_name,
            providers=providers or ["CoreMLExecutionProvider", "CPUExecutionProvider"],
        )
        self.app.prepare(ctx_id=0, det_size=(det_size, det_size))

    def detect(self, pil_rgb):
        """PIL RGB → lista di (embedding normed[512], det_score, bbox xyxy) sopra `min_score`."""
        bgr = np.asarray(pil_rgb)[:, :, ::-1]  # insightface segue la convenzione BGR di OpenCV
        out = []
        for f in self.app.get(bgr):
            if f.det_score < self.min_score:
                continue
            x1, y1, x2, y2 = (int(v) for v in f.bbox)
            out.append((f.normed_embedding.astype(np.float32), float(f.det_score), (x1, y1, x2, y2)))
        return out


def load_gallery(gallery_dir, recognizer):
    """Legge `<dir>/<Nome>/*.{jpg,png,webp}` → {nome: centroide embedding normalizzato}.

    Ogni sotto-cartella è un personaggio; per foto si prende il volto con det_score più alto,
    poi si media (e normalizza) sugli scatti del personaggio. Le cartelle senza volti sono ignorate.
    """
    from PIL import Image

    gdir = Path(gallery_dir)
    gallery = {}
    for person in sorted(p for p in gdir.iterdir() if p.is_dir()):
        embs = []
        for img in sorted(person.glob("*")):
            if img.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            faces = recognizer.detect(Image.open(img).convert("RGB"))
            if faces:
                embs.append(max(faces, key=lambda t: t[1])[0])
        if embs:
            m = np.mean(embs, axis=0)
            gallery[person.name] = m / (np.linalg.norm(m) + 1e-9)
    return gallery


def _crop_thumb(pil_rgb, bbox, pad=0.3, size=112):
    """Crop quadrato del volto (con margine) ridimensionato a `size`×`size`."""
    x1, y1, x2, y2 = bbox
    w, h = x2 - x1, y2 - y1
    cx, cy = x1 + w / 2, y1 + h / 2
    half = max(w, h) * (1 + pad) / 2
    box = (int(cx - half), int(cy - half), int(cx + half), int(cy + half))
    return pil_rgb.crop(box).resize((size, size))


# Sotto questa mediana di `det_score` il cluster non è un'identità: è roba che il rilevatore non
# riconosce come volto umano. Non è una taratura sul film ma sul rilevatore — SCRFD è calibrato sui
# volti, e sotto ~0,65 sta dicendo "non so se è una faccia".
#
# Misurato su *Rogue One* (plan/DA-FARE.md §2): il cluster che fonde K-2SO, Darth Vader, gli
# stormtrooper e un pilota con la visiera ha mediana **0,579**, contro **0,762** di tutti gli altri,
# e il suo p90 (0,68) sta sotto il p10 di ogni cluster legittimo (0,69). Nessuna soglia di
# clustering li separa e nessun encoder di apparenza li salva: qui si segnala e basta.
UNCERTAIN_DET = 0.65


# Un cluster insegna l'invarianza cross-shot solo se ricorre: sotto questo numero di shot
# distinti non ha visto abbastanza luci e pose per dire cosa *non* conta.
TEACHER_MIN_SHOTS = 3


def mark_uncertain(cast, labels, det_scores):
    """Segna `uncertain` i cluster che il rilevatore non considera volti. -> quanti segnati.

    Marcati, non scartati: restano visibili e rinominabili nella UI — ma **fuori dal prompt del
    VLM**, o un nome sbagliato finisce nella descrizione di decine di shot.
    """
    labels = np.asarray(labels)
    det_scores = np.asarray(det_scores)
    n = 0
    for c in cast:
        med = float(np.median(det_scores[labels == c["id"]]))
        c["det_median"] = round(med, 3)
        if med < UNCERTAIN_DET:
            c["uncertain"] = True
            n += 1
    return n


def split_by_reliability(labels, det_scores, shot_indices, min_shots=TEACHER_MIN_SHOTS):
    """Divide i cluster fra maestri e sospetti secondo `UNCERTAIN_DET`. -> (ids_maestri, sospetti).

    Stessa soglia di `mark_uncertain`, letta nei due versi: sopra, ArcFace sta riconoscendo
    volti umani e le sue etichette sono un buon segnale di identita' cross-shot; sotto, sta
    dicendo «non so se e' una faccia» e li' vanno rimessi in discussione.

    `ids_maestri[N]`: identita' per volto, `-1` per chi non insegna — la forma che vuole
    `adapt.train_adapter`. Un maestro deve anche ricorrere in >= `min_shots` shot distinti.
    """
    labels = np.asarray(labels)
    det_scores = np.asarray(det_scores)
    shots = np.asarray(shot_indices)

    ids = np.full(len(labels), -1, dtype=int)
    sospetti = set()
    for c in sorted({int(l) for l in labels if l >= 0}):
        m = labels == c
        if float(np.median(det_scores[m])) < UNCERTAIN_DET:
            sospetti.add(c)
        elif len(np.unique(shots[m])) >= min_shots:
            ids[m] = c
    return ids, sospetti


def _refine(labels, scores, shot_idx, body, threshold=0.70):
    """Ri-clusterizza i cluster sospetti nello spazio adattato. -> (labels, spezzati).

    Tre passi, e ognuno puo' non fare niente senza rompere il resto: si scelgono i maestri, si
    addestra la testa sui loro embedding di figura, si rimettono in discussione i sospetti.

    ⚠️ `threshold` **non** e' `faces_threshold`: quella vive nello spazio ArcFace, questa nello
    spazio DINOv2 adattato, e le due distribuzioni di similarita' non sono commensurabili.
    Passare 0,50 qui lascia tutti i sospetti in un gruppo solo (purezza 0,43 contro 0,98 a 0,70,
    misurato con verita' annotata su *Rogue One*).
    """
    from .adapt import project, train_adapter
    from .identify import refine_clusters

    ids, sospetti = split_by_reliability(labels, scores, shot_idx)
    if not sospetti:
        return labels, set()
    W = train_adapter(body, ids)
    if W is None:
        return labels, set()   # meno di due identita' maestre: non c'e' niente da imparare
    return refine_clusters(labels, project(body, W), sospetti, threshold)


def recognize_characters(manifest, video, recognizer, *, gallery=None, n_frames=6, size=640,
                         threshold=0.5, min_shots=2, min_face_px=50, film_dir=None,
                         encoder=None, refine_threshold=0.70, progress=True):
    """Popola `manifest["cast"]` e `shot["characters"]` rilevando e clusterizzando i volti del film.

    Campiona `n_frames` per shot (via `sample_frames`), rileva volti + embedding e clusterizza
    **a due stadi** (`cluster_two_stage`): prima dentro ogni shot col vincolo must-not-link, poi
    sugli embedding mediati dei gruppi. Con `gallery` mappa i cluster ai nomi reali. Salva una
    thumbnail per personaggio in `<film_dir>/faces/`. Ritorna (n_volti, n_personaggi).

    `min_face_px`: lato minimo del bbox. Nel cinema gran parte delle detection sono volti
    lontani o di scorcio, il cui embedding e' rumore: si scartano prima di clusterizzare.

    `encoder`: con un `embed.BodyEncoder`, i cluster che ArcFace non riconosce come volti umani
    (droidi, elmetti) vengono rimessi in discussione sui ritagli di **figura** — vedi `_refine`.
    I frame sono gia' in mano qui, quindi non costa nessuna estrazione in piu'.
    """
    from tqdm import tqdm

    from ..captioning.caption import sample_frames  # riuso l'estrazione frame via ffmpeg

    shots = manifest["shots"]
    detected: list[DetectedFace] = []
    for shot in tqdm(shots, desc="[faces]", unit="shot", disable=not progress):
        frames = sample_frames(video, shot["start_time"], shot["end_time"], n_frames, size,
                               manifest.get("fps"))
        for fi, pil in enumerate(frames):
            for emb, score, bbox in recognizer.detect(pil):
                x1, y1, x2, y2 = bbox
                if min(x2 - x1, y2 - y1) < min_face_px:
                    continue  # volto troppo piccolo: l'embedding e' rumore che avvelena i cluster
                detected.append(DetectedFace(shot["index"], fi, emb, score,
                                             _crop_thumb(pil, bbox)))
                if encoder is not None:
                    encoder.add(pil, bbox)   # stesso ordine di `detected`

    if not detected:
        manifest["cast"] = []
        for shot in shots:
            shot["characters"] = []
        return 0, 0

    emb = np.stack([d.embedding for d in detected])
    scores = np.array([d.det_score for d in detected])
    shot_idx = [d.shot_index for d in detected]
    labels = cluster_two_stage(emb, shot_idx, [d.frame_index for d in detected],
                               threshold, det_scores=scores)

    spezzati = set()
    if encoder is not None:
        labels, spezzati = _refine(labels, scores, shot_idx, encoder.result(), refine_threshold)

    names = match_gallery(centroids_of(emb, labels), gallery, threshold) if gallery else {}
    cast, per_shot = build_cast(labels, shot_idx, names, min_shots)
    mark_uncertain(cast, labels, scores)
    for c in cast:
        if c["id"] in spezzati:
            c["refined"] = True

    if film_dir is not None and cast:
        kept = {c["id"] for c in cast}
        best: dict[int, DetectedFace] = {}
        for d, lab in zip(detected, labels):
            lab = int(lab)
            if lab in kept and (lab not in best or d.det_score > best[lab].det_score):
                best[lab] = d
        faces_dir = Path(film_dir) / "faces"
        faces_dir.mkdir(parents=True, exist_ok=True)
        for c in cast:
            best[c["id"]].thumb.save(faces_dir / f"{c['id']}.png")
            c["thumb"] = f"faces/{c['id']}.png"

    manifest["cast"] = cast
    for shot in shots:
        shot["characters"] = sorted(per_shot.get(shot["index"], set()))
    return len(detected), len(cast)
