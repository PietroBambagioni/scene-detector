from __future__ import annotations

import json
from pathlib import Path


def build_manifest(video_info, scenes, detector, clip_template="scene-{:03d}.mp4",
                   video_src=None):
    """Costruisce il manifest del catalogo shot (backbone per ASR / VLM / UI).

    I campi `description` e `dialogue` sono placeholder, riempiti dagli step successivi.
    `clip_template=None` (`--split-mode none`): nessuna clip su disco, `clip` resta `None` e
    `video_src` dice alla UI come raggiungere il film originale per i media fragments.
    """
    return {
        "video": Path(video_info.path).name,
        **({"video_src": video_src} if video_src else {}),
        "fps": video_info.fps,
        "n_frames": video_info.n_frames,
        "duration": video_info.duration,
        "detector": detector,
        "n_shots": len(scenes),
        "cast": [],
        "shots": [
            {
                "index": s.index,
                "start_frame": s.start_frame,
                "end_frame": s.end_frame,
                "start_time": round(s.start_time, 3),
                "end_time": round(s.end_time, 3),
                "clip": clip_template.format(s.index + 1) if clip_template else None,
                "confidence": s.confidence,
                # presente solo quando lo shot si apre con una transizione graduale
                **({"transition": {"start_frame": s.transition[0], "end_frame": s.transition[1],
                                   "n_frames": s.transition[1] - s.transition[0] + 1}}
                   if s.transition else {}),
                "description": None,
                "dialogue": None,
                "characters": [],
            }
            for s in scenes
        ],
    }


# Campi che costano ore di calcolo e che `build_manifest` non può ricostruire: se il manifest
# nuovo li lasciasse a `None`, un run senza `--vlm`/`--asr` **cancellerebbe** il lavoro dei run
# precedenti. È già successo: `clips/Rogue.One/manifest.json` ha perso 3204 descrizioni e 897
# dialoghi (5h16m) in un run `--scenes`, e si sono recuperati solo perché esistevano due copie
# fatte a mano. Il cast non è qui perché lo step `faces` ha già il suo resume.
CAMPI_COSTOSI = ("description", "dialogue", "characters", "speakers")


def merge_prior(manifest, path):
    """Riporta nel manifest i campi costosi già presenti su disco. -> quanti shot recuperati.

    Accoppiamento per `index`, e solo dove il valore nuovo è vuoto: un run che ricalcola davvero
    (`--vlm`, `--asr`, `--diarize`) scrive dopo e vince. Se il manifest su disco non c'è o è
    illeggibile non è un errore — è il primo run.
    """
    p = Path(path)
    if not p.exists():
        return 0
    try:
        prior = load_manifest(p)
    except (json.JSONDecodeError, OSError):
        return 0

    by_index = {s["index"]: s for s in prior.get("shots", [])}
    n = 0
    for shot in manifest["shots"]:
        old = by_index.get(shot["index"])
        if not old:
            continue
        recuperati = [c for c in CAMPI_COSTOSI if not shot.get(c) and old.get(c)]
        for campo in recuperati:
            shot[campo] = old[campo]
        n += bool(recuperati)
    return n


def write_manifest(manifest, path):
    Path(path).write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def load_manifest(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
