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


def recognize_characters(manifest, video, recognizer, *, gallery=None, n_frames=6, size=640,
                         threshold=0.5, min_shots=2, min_face_px=50, film_dir=None,
                         progress=True):
    """Popola `manifest["cast"]` e `shot["characters"]` rilevando e clusterizzando i volti del film.

    Campiona `n_frames` per shot (via `sample_frames`), rileva volti + embedding e clusterizza
    **a due stadi** (`cluster_two_stage`): prima dentro ogni shot col vincolo must-not-link, poi
    sugli embedding mediati dei gruppi. Con `gallery` mappa i cluster ai nomi reali. Salva una
    thumbnail per personaggio in `<film_dir>/faces/`. Ritorna (n_volti, n_personaggi).

    `min_face_px`: lato minimo del bbox. Nel cinema gran parte delle detection sono volti
    lontani o di scorcio, il cui embedding e' rumore: si scartano prima di clusterizzare.
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

    names = match_gallery(centroids_of(emb, labels), gallery, threshold) if gallery else {}
    cast, per_shot = build_cast(labels, shot_idx, names, min_shots)

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
