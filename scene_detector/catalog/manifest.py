from __future__ import annotations

import json
import os
from pathlib import Path


def build_manifest(video_info, scenes, detector, clip_template="clip/scene-{:03d}.mp4",
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
# fatte a mano. Il cast non è qui perché non sta sugli shot: lo riporta `merge_film_keys`.
# `rivisto` non costa ore di GPU ma ore di persona: e' il segno «questo confine l'ho guardato»
# della modalita' revisione, e perderlo vuol dire riguardare la coda da capo.
CAMPI_COSTOSI = ("description", "dialogue", "characters", "speakers", "rivisto")


def merge_prior(manifest, path):
    """Riporta nel manifest i campi costosi già presenti su disco. -> quanti shot recuperati.

    Accoppiamento per **range** (`start_frame`, `end_frame`), e solo dove il valore nuovo è vuoto:
    un run che ricalcola davvero (`--vlm`, `--asr`, `--diarize`) scrive dopo e vince. Se il
    manifest su disco non c'è o è illeggibile non è un errore — è il primo run.

    `index` non è un'identità: basta un taglio manuale nella UI (o una soglia diversa) e ogni
    indice a valle scala di uno, così le descrizioni scivolano tutte sullo shot sbagliato. Un
    campo **assegnato male** è peggio di un campo perso, perché non si vede. E non basta
    l'inizio: con una soglia diversa lo shot [s, e] diventa [s, e'] e la descrizione del pezzo
    vecchio finiva su quello nuovo — su *Anna* 281 shot su 307 con la descrizione della loro
    prima metà (VERBALE §3.6 ter). Se si è mosso uno dei due confini il recupero non avviene.

    Unica eccezione, `rivisto`: dice «il confine che **apre** lo shot l'ho guardato», non parla
    del contenuto, quindi accoppia sul solo `start_frame`.
    """
    p = Path(path)
    if not p.exists():
        return 0
    try:
        prior = load_manifest(p)
    except (json.JSONDecodeError, OSError):
        return 0

    vecchi = [s for s in prior.get("shots", []) if s.get("start_frame") is not None]
    by_range = {(s["start_frame"], s.get("end_frame")): s for s in vecchi}
    by_start = {s["start_frame"]: s for s in vecchi}
    n = 0
    for shot in manifest["shots"]:
        stesso = by_range.get((shot.get("start_frame"), shot.get("end_frame"))) or {}
        fonte = {c: stesso for c in CAMPI_COSTOSI}
        fonte["rivisto"] = by_start.get(shot.get("start_frame")) or {}
        recuperati = [c for c in CAMPI_COSTOSI if not shot.get(c) and fonte[c].get(c)]
        for campo in recuperati:
            shot[campo] = fonte[campo][campo]
        n += bool(recuperati)
    return n


def merge_scene_names(manifest, path):
    """Riporta i nomi delle scene battezzati a mano nella UI. -> quanti recuperati.

    Stessa regola degli shot: accoppiamento per **`start_frame`**, mai per indice. Un run con
    `--scenes` rifà il raggruppamento da zero e il nome scomparirebbe; se il confine si è mosso
    il nome non torna, ed è giusto — parlava di un'altra porzione di film.
    """
    p = Path(path)
    if not p.exists() or not manifest.get("scenes"):
        return 0
    try:
        prior = load_manifest(p)
    except (json.JSONDecodeError, OSError):
        return 0

    by_start = {s["start_frame"]: s["name"] for s in prior.get("scenes", [])
                if s.get("name") and s.get("start_frame") is not None}
    n = 0
    for sc in manifest["scenes"]:
        nome = by_start.get(sc.get("start_frame"))
        if nome and not sc.get("name"):
            sc["name"] = nome
            n += 1
    return n


# Ciò che sta **sopra** gli shot e che `build_manifest` non ricostruisce: il cast (ore di volti,
# più i nomi dati a mano), le scene (corrette a mano nella UI), il numero di parlanti.
CHIAVI_FILM = ("cast", "scenes", "n_scenes", "n_speakers")


def load_prior(path):
    """Il manifest già su disco, o `None` se non c'è o è illeggibile: è il primo run, non un errore."""
    try:
        return load_manifest(path)
    except (json.JSONDecodeError, OSError):
        return None


def merge_film_keys(manifest, prior):
    """Riporta `CHIAVI_FILM` da un manifest precedente con **gli stessi shot**. -> chiavi riportate.

    È `merge_prior` un livello sopra, e copre lo stesso buco: un run che non riaccende `--faces`
    o `--scenes` ripartiva da `cast: []` e senza scene, lasciando negli shot gli id di personaggi
    che non esistono più — su *Anna* 29 personaggi e 35 scene azzerati da un `--vlm` da solo. Il
    recupero c'era già, ma solo per `--from-manifest`.

    **Solo se i range coincidono tutti.** Le scene puntano agli shot per indice (`first_shot`,
    `last_shot`), e un cast contato su altri shot dichiara presenze che non valgono più: con i
    confini spostati non torna niente, per la stessa ragione di `merge_prior` — un campo assegnato
    male è peggio di uno perso. Dove il valore nuovo c'è già non si tocca: lo step vero
    (`--faces`, `--scenes`, `--diarize`) gira dopo e vince.
    """
    def ranges(m):
        return [(s.get("start_frame"), s.get("end_frame")) for s in m.get("shots", [])]

    if not prior or ranges(prior) != ranges(manifest):
        return []
    chiavi = [k for k in CHIAVI_FILM if prior.get(k) and not manifest.get(k)]
    for k in chiavi:
        manifest[k] = prior[k]
    return chiavi


def write_manifest(manifest, path):
    # Temporaneo + rename, che è atomico: il VLM riscrive il manifest a ogni shot, e un Ctrl-C a
    # metà scrittura lasciava un JSON troncato — che `merge_prior` legge come «primo run» e
    # ricomincia da zero, in silenzio, buttando ore di descrizioni.
    tmp = Path(path).with_name(Path(path).name + ".part")
    tmp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def load_manifest(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
