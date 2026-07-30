from __future__ import annotations

from pathlib import Path


def extract_thumbs(manifest, video, film_dir, size=256, progress=True):
    """Un fotogramma per shot in `<film_dir>/thumbs/`, path relativo in `shot["thumb"]`.

    **Per shot e non per scena**, ed è la scelta che fa funzionare l'editing dei confini nella UI:
    una scena nata da un'unione o da una divisione prende la miniatura del suo primo shot, sempre.
    Se le miniature stessero sulle scene, ogni divisione ne creerebbe una senza immagine.

    Stessa convenzione delle facce (`recognition/faces.py`): sottocartella del catalogo, path
    relativo nel manifest. JPEG e non PNG perché sono fotogrammi: ~10 KB contro ~100, e su 3200
    shot sono 30 MB invece di 300.

    Idempotente: salta gli shot che hanno già il file su disco.
    """
    from tqdm import tqdm

    from ..captioning.caption import sample_frames

    dest = Path(film_dir) / "thumbs"
    dest.mkdir(parents=True, exist_ok=True)
    fps = manifest.get("fps")
    shots = manifest["shots"]
    n = 0
    for shot in tqdm(shots, desc="[thumbs]", unit="shot", disable=not progress):
        rel = f"thumbs/{shot['index']:06d}.jpg"
        path = Path(film_dir) / rel
        if not path.exists():
            # n=1 -> il frame di mezzo dello shot; `fps` evita di finire su quello dopo
            frame = sample_frames(video, shot["start_time"], shot["end_time"], 1, size, fps)[0]
            frame.save(path, quality=80)
            n += 1
        shot["thumb"] = rel
    return n
