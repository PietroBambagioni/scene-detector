"""Pesi neurali: registro e download.

I pesi non stanno nel repo (`weights/` è in `.gitignore`) e l'upstream non pubblica un
artefatto scaricabile: TransNetV2 va convertito da TensorFlow. C'è però un mirror pubblico su
HuggingFace che serve **gli stessi pesi** di quelli validati in locale: una conversione diversa
(serializzazione torch differente) ma con 90/90 tensori uguali — verificato.

Lo sha256 è quello del file sul mirror: se un mirror cambia contenuto, il download fallisce
invece di installare pesi ignoti.
"""
from __future__ import annotations

import hashlib
import shutil
import urllib.request
from pathlib import Path

WEIGHTS_DIR = Path("weights")

# nome -> (url, sha256, file di destinazione)
REGISTRY = {
    "transnetv2": (
        "https://huggingface.co/MiaoshouAI/transnetv2-pytorch-weights/resolve/main/transnetv2-pytorch-weights.pth",
        "46520d66d4bf60414a4d82e0e94a92442ff950e34517a3718b2e54815e642b53",
        "transnetv2.pth",
    ),
}


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(name, weights_dir=WEIGHTS_DIR, force=False, on_progress=None):
    """Scarica il peso `name` in `weights_dir`, verificandone lo sha256.

    Se il file esiste già non viene toccato (`force=True` per riscaricarlo): chi ha convertito
    i pesi a mano ha un file valido ma con hash diverso dal mirror, e non va sovrascritto.
    Scrive su un temporaneo e rinomina solo dopo la verifica: un download interrotto non lascia
    un peso corrotto al suo posto. Ritorna il Path del file.
    """
    url, digest, filename = REGISTRY[name]
    dest = Path(weights_dir) / filename
    if dest.exists() and not force:
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if on_progress:
                on_progress(name, done, total)

    got = _sha256(tmp)
    if got != digest:
        tmp.unlink()
        raise RuntimeError(f"{name}: sha256 {got[:12]}… non corrisponde a {digest[:12]}… ({url})")
    tmp.replace(dest)
    return dest


def missing_tools():
    """Gli eseguibili esterni richiesti che non sono nel PATH."""
    return [t for t in ("ffmpeg", "ffprobe") if shutil.which(t) is None]
