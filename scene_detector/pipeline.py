from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

from .core import telemetry as tel_mod
from .core.config import Config, SplitMode
from .core.cpu import resolve_workers
from .core.scene import enforce_min_len
from .core.telemetry import log
from .detection import build_detector
from .io.video import probe
from .segmentation.splitter import split


def _shots_corretti(path, info):
    """Legge un manifest corretto a mano e controlla che descriva *questo* film. -> manifest.

    È l'unico ingresso della pipeline che non arriva dal nostro codice: un JSON riferito a un
    altro film, o con i range rotti da una modifica a mano, taglierebbe le clip nei punti
    sbagliati **senza dire niente**. I controlli sono gli stessi invarianti del resto del
    progetto: range contigui, `end_frame` inclusivo, copertura dal frame 0.
    """
    from .catalog.manifest import load_manifest

    m = load_manifest(path)
    shots = m.get("shots") or []
    if not shots:
        raise ValueError(f"{path}: nessuno shot")
    if abs(m.get("fps", 0) - info.fps) > 1e-3:
        raise ValueError(f"{path}: fps {m.get('fps')} contro {info.fps} del video — altro film?")
    for a, b in zip(shots, shots[1:]):
        if b["start_frame"] != a["end_frame"] + 1:
            raise ValueError(f"{path}: shot non contigui fra #{a['index']} (fine {a['end_frame']}) "
                             f"e #{b['index']} (inizio {b['start_frame']})")
    # la contiguità da sola non basta: (0,9) (10,5) (6,99) è contigua e ha uno shot rovesciato
    for s in shots:
        if s["end_frame"] < s["start_frame"]:
            raise ValueError(f"{path}: shot #{s['index']} rovesciato "
                             f"({s['start_frame']}–{s['end_frame']})")
    if shots[0]["start_frame"] != 0 or shots[-1]["end_frame"] >= info.n_frames:
        raise ValueError(f"{path}: i range escono dal video (0–{info.n_frames - 1})")
    # «coprono tutti i frame» vale anche in coda: un manifest che finisce prima lascerebbe la fine
    # del film fuori dal catalogo, senza un errore
    if shots[-1]["end_frame"] != info.n_frames - 1:
        raise ValueError(f"{path}: l'ultimo shot finisce a {shots[-1]['end_frame']}, il video a "
                         f"{info.n_frames - 1} — la coda resterebbe scoperta")
    return m


def _scene_corrette(m, fps):
    """Gli shot di un manifest corretto -> list[Scene], con confidenza e transizione **portate**.

    Senza, ogni shot ripartiva da `confidence=1.0` e senza `transition`: dopo il primo ritaglio
    la coda di revisione si svuotava e il manifest dichiarava certo ogni confine. Lo shot
    tagliato a mano arriva dalla UI con `confidence: null`, e resta tale.
    """
    from .core.scene import scenes_from_ranges

    shots = m["shots"]
    return scenes_from_ranges(
        [(s["start_frame"], s["end_frame"]) for s in shots], fps, source="manuale",
        confidences=[s.get("confidence", 1.0) for s in shots],
        transitions=[(t["start_frame"], t["end_frame"]) if (t := s.get("transition")) else None
                     for s in shots])


def _parametri_volti(cfg):
    """I parametri da cui dipende un cast: cambiarne uno ne darebbe un altro."""
    return {k: str(v) if isinstance(v, Path) else v
            for k, v in asdict(cfg).items() if k.startswith("faces_")}


def _riusa_cast(manifest, prior, params):
    """Resume dei volti: riporta il cast e i parametri con cui è nato. -> le differenze dai
    parametri di questo run (`[]` se nessuna o se non erano registrati), `None` senza un cast.

    Il resume non ri-rileva niente, quindi i parametri di *questo* run non si applicano: senza
    dirlo, `--faces-min-shots 3` su un cast nato con 2 sembra aver funzionato e ne lascia 113
    dove ne vorrebbe 65 (*Rogue One*, VERBALE §4.11). Si avvisa e non si ricalcola: rifare i
    volti butterebbe nomi e fusioni fatti a mano nella UI.
    """
    if not (prior and prior.get("cast")):
        return None
    manifest["cast"] = prior["cast"]
    nati = prior.get("cast_params")
    if not nati:
        return []
    manifest["cast_params"] = nati
    return [f"{k} {nati.get(k)} → {v}" for k, v in params.items() if nati.get(k) != v]


def run(cfg: Config) -> None:
    """Orchestrazione end-to-end: detection → split → (faces) → (ASR) → (VLM) → manifest/UI → galleria.

    Tutti i parametri del run vivono in `cfg` (`cli` lo popola dai flag Typer).
    """
    info = probe(cfg.video)
    out_dir = cfg.output_dir / cfg.video.stem

    tel = tel_mod.Telemetry(out_dir)
    log.info("[probe] %d frame @ %.3f fps, %.1fs", info.n_frames, info.fps, info.duration)

    split_workers = resolve_workers(cfg.jobs)
    asr_workers = resolve_workers(cfg.asr_threads) if cfg.asr else None
    env = tel_mod.collect_env()
    tel.write_config({
        "command": tel_mod.command_snapshot(),
        # la `Config` intera, non un elenco ricopiato a mano: quello restava indietro, e mancavano
        # proprio `faces_min_shots` e `faces_min_px`, i due che dicono con cosa è nato un cast
        "flags": asdict(cfg),
        "mode": {
            "detector": cfg.detector.value,
            "split_mode": cfg.split_mode.value,
            "device": "mps" if env.get("mps_available") else "cpu",
            "split_workers": split_workers, "asr_workers": asr_workers,
        },
        "video": {
            "name": cfg.video.name, "fps": info.fps, "n_frames": info.n_frames,
            "duration": info.duration, "width": info.width, "height": info.height,
        },
        "env": env,
    })

    n_steps = (4 + (1 if cfg.scenes else 0) + (1 if cfg.faces else 0)
               + (1 if cfg.asr else 0) + (1 if cfg.diarize else 0) + (1 if cfg.vlm else 0))

    # I confini corretti a mano nella UI sostituiscono il detector, e **solo** quello: da qui in
    # giù la pipeline non sa la differenza, quindi split, miniature, manifest e UI ripartono dai
    # confini nuovi senza un ramo in più. `enforce_min_len` non si applica — la fusione cieca
    # degli shot brevi qui mangerebbe proprio i tagli appena scelti a mano.
    corretto = _shots_corretti(cfg.from_manifest, info) if cfg.from_manifest else None

    log.info("[1/%d] %s…", n_steps, "Confini dal manifest" if corretto else "Rilevamento shot")
    with tel.step("detection") as o:
        if corretto:
            scenes = _scene_corrette(corretto, info.fps)
            o["from_manifest"] = str(cfg.from_manifest)
        else:
            scenes = build_detector(cfg.detector, cfg).detect(info)
            scenes = enforce_min_len(scenes, cfg.min_scene_len)
            o["threshold"] = cfg.threshold
            o["min_peak"] = cfg.min_peak
        o["n_shots"] = len(scenes)
    log.info("  %d shot", len(scenes))

    cutting = cfg.split_mode is not SplitMode.none
    with tel.step("split") as o:
        if cutting:
            log.info("[2/%d] Taglio %d clip…", n_steps, len(scenes))
            orfane = split(info, scenes, out_dir / "clip", cfg.split_mode, jobs=cfg.jobs)
            o["n_clips"] = len(scenes)
            o["n_orfane"] = orfane
            if orfane:
                log.info("  %d clip in eccesso rinominate .orfano (il run precedente ne aveva "
                         "di più)", orfane)
        else:
            log.info("[2/%d] Taglio saltato (--split-mode none): la UI riproduce il film intero",
                     n_steps)
            o["n_clips"] = 0
        o["split_mode"] = cfg.split_mode.value
        o["workers"] = split_workers

    from .catalog.manifest import (build_manifest, load_prior, merge_film_keys, merge_prior,
                                   write_manifest)
    label = cfg.detector.value
    # La UI riproduce **sempre** il film originale: le serve come raggiungerlo dalla cartella del
    # catalogo (relativo: catalogo e film restano spostabili insieme). Anche con le clip su disco,
    # perché `--split-mode copy` le apre al keyframe precedente allo `start_frame` — fino a un GOP
    # prima — e il contatore di frame della UI, che misura da inizio clip, sballa di altrettanto:
    # su *Anna* (keyframe ogni ~1 s) 2-4 frame, con GOP da 2 s sono ±2 s. «✂ taglia qui» scriveva
    # nel manifest il frame sbagliato, e il ritaglio frame-accurate lo eseguiva fedelmente.
    video_src = os.path.relpath(Path(cfg.video).resolve(), out_dir.resolve())
    manifest = build_manifest(info, scenes, label,
                              # deve combaciare con la cartella passata a `split` qui sopra: il
                              # path nel manifest è relativo a `index.html`, che sta in out_dir
                              clip_template=None if not cutting else "clip/scene-{:03d}.mp4",
                              video_src=video_src)
    manifest_path = out_dir / "manifest.json"
    # `build_manifest` riparte da zero: senza questo, un run che non riaccende `--vlm`/`--asr`
    # sovrascrive descrizioni e dialoghi con `None` e butta ore di calcolo. Col ritaglio manuale
    # la sorgente è il JSON corretto e non quello su disco: è lo stesso, più le modifiche.
    recuperati = merge_prior(manifest, cfg.from_manifest or manifest_path)
    if recuperati:
        log.info("[resume] %d shot recuperati dal manifest esistente", recuperati)

    # Roba che `build_manifest` non ricostruisce e che un run non deve buttare: il cast coi nomi
    # digitati a mano e le scene corrette nella UI. Valeva solo per il ritaglio manuale, quindi un
    # `--vlm` da solo azzerava cast e scene. Stessa sorgente di `merge_prior` qui sopra.
    prior = corretto or load_prior(manifest_path)
    riportate = merge_film_keys(manifest, prior)
    if riportate:
        log.info("[resume] dal manifest esistente: %s", ", ".join(riportate))

    # Miniature **per shot** e sempre, non solo con `--scenes`: la lista della UI le mostra in
    # entrambe le modalità (senza, resta una fila di testo), e con le scene fanno anche le
    # intestazioni — per shot perché unisci/dividi possono far cominciare una scena da qualunque.
    log.info("[3/%d] Miniature per shot…", n_steps)
    with tel.step("thumbs") as o:
        from .catalog.thumbs import extract_thumbs
        # ponytail: un seek ffmpeg per shot, ~0,1 s ciascuno — quindi ~5 min su 3200 shot, niente
        # accanto ai 45 min di ASR+VLM ma visibile su un run di sola detection. Idempotente (i
        # file già su disco si saltano). Se il costo mordesse, il rimedio è un `--no-thumbs`.
        o["n_thumbs"] = extract_thumbs(manifest, cfg.video, out_dir)
    log.info("  %d miniature (%d già su disco)", o["n_thumbs"], len(scenes) - o["n_thumbs"])
    step = 3

    if cfg.scenes:
        step += 1
        log.info("[%d/%d] Raggruppamento in scene…", step, n_steps)
        if cfg.n_scenes is None:
            # misurato su RAI: il gomito dei valori singolari dà in media 7,2 scene dove ce ne
            # sono 12,6, e non segue il video (GT 22 -> stima 5). Vedi plan/VERBALE.md §5.10.
            log.warning("  --n-scenes non impostato: la stima automatica sottostima di ~40%%")
        with tel.step("grouping") as o:
            from .detection.neural import read_small_frames
            from .grouping import build_scene_entries, group_shots, shot_signatures
            # Feature: istogrammi HSV finché il banco RAI (`prove/rai_scene_ab.py`) non dice che
            # `siglip_signatures` vince — a quel punto cambia solo questa riga.
            # ponytail: seconda passata di decode a 48×27. Sono gli stessi frame della detection,
            # ma solo il detector neurale li espone (`detect_from_frames`): condividerli costa più
            # plumbing del minuto che risparmia.
            frames = read_small_frames(cfg.video, 48, 27, total=info.n_frames,
                                       desc="[grouping] frames")
            groups = group_shots(scenes, shot_signatures(frames, scenes), cfg.n_scenes)
            manifest["n_scenes"] = len(groups)
            manifest["scenes"] = build_scene_entries(groups, scenes)
            # il raggruppamento riparte da zero: senza questo un nome scritto nella UI vive
            # quanto il run successivo
            from .catalog.manifest import merge_scene_names
            o["nomi_recuperati"] = merge_scene_names(manifest, cfg.from_manifest or manifest_path)
            o["n_scenes"] = len(groups)
            o["n_scenes_richiesto"] = cfg.n_scenes
            o["shot_per_scena"] = round(len(scenes) / len(groups), 2)
        log.info("  %d shot → %d scene", len(scenes), len(groups))

    if cfg.faces:
        step += 1
        log.info("[%d/%d] Riconoscimento personaggi…", step, n_steps)
        with tel.step("faces") as o:
            params = _parametri_volti(cfg)
            # resume: riusa il cast già calcolato (+ eventuali rinomine). `prior` è il JSON
            # corretto a mano quando c'è: rileggendo sempre da disco, i nomi dati nella UI
            # perdevano contro la copia più vecchia.
            diversi = _riusa_cast(manifest, prior, params)
            if diversi is not None:
                rifare = (f"togli la voce `cast` da {cfg.from_manifest or manifest_path} "
                          "per rifare i volti")
                if diversi:
                    log.warning("  cast riusato dal manifest, nato con altri parametri: %s — "
                                "quelli di questo run non sono applicati (%s)",
                                ", ".join(diversi), rifare)
                elif "cast_params" not in manifest:
                    log.info("  cast riusato dal manifest; i parametri con cui è nato non sono "
                             "registrati")
                    if cfg.faces_refine:
                        log.warning("  --faces-refine non applicato (%s)", rifare)
                if "cast" not in riportate:
                    log.warning("  i confini sono cambiati dal run che ha fatto il cast: gli shot "
                                "nuovi restano senza personaggi (%s)", rifare)
                # I `characters` per shot **non** si toccano qui: li ha già rimessi `merge_prior`
                # accoppiando per range (inizio e fine). Questo ramo li riassegnava per `index`,
                # che non è un'identità: bastava un run con una soglia diversa (592 shot → 307 su *Anna*) e
                # 356 shot prendevano i personaggi di un altro pezzo di film, **in silenzio** —
                # sovrascrivendo per giunta il recupero corretto fatto poche righe sopra.
                n_faces, n_chars = 0, len(manifest["cast"])
            else:
                write_manifest(manifest, manifest_path)  # persisti prima (crash-safe)
                from .recognition import FaceRecognizer, load_gallery, recognize_characters
                recognizer = FaceRecognizer(min_score=cfg.faces_min_score)
                gallery = load_gallery(cfg.faces_gallery, recognizer) if cfg.faces_gallery else None
                encoder = None
                if cfg.faces_refine:
                    from .recognition.embed import BodyEncoder
                    encoder = BodyEncoder()
                n_faces, n_chars = recognize_characters(
                    manifest, cfg.video, recognizer, gallery=gallery, n_frames=cfg.faces_frames,
                    threshold=cfg.faces_threshold, min_shots=cfg.faces_min_shots,
                    min_face_px=cfg.faces_min_px, film_dir=out_dir, encoder=encoder,
                    refine_threshold=cfg.faces_refine_threshold,
                )
                manifest["cast_params"] = params
            o["n_faces"] = n_faces
            o["n_characters"] = n_chars
            o["gallery"] = str(cfg.faces_gallery) if cfg.faces_gallery else None
        log.info("  %d volti → %d personaggi", n_faces, n_chars)

    if cfg.asr:
        step += 1
        log.info("[%d/%d] Trascrizione dialoghi (%s)…", step, n_steps, cfg.asr_model)
        with tel.step("asr") as o:
            from .transcription.asr import transcribe
            from .transcription.align import assign_dialogue
            segments, lang = transcribe(cfg.video, cfg.asr_model, language=cfg.asr_lang,
                                        cpu_threads=cfg.asr_threads)
            assign_dialogue(manifest["shots"], segments)
            o["language"] = lang
            o["n_segments"] = len(segments)
            o["n_shots_with_dialogue"] = sum(1 for s in manifest["shots"] if s.get("dialogue"))
            o["model"] = cfg.asr_model
            o["threads"] = asr_workers
        log.info("  lingua=%s, %d segmenti", lang, len(segments))

    if cfg.diarize:
        step += 1
        log.info("[%d/%d] Diarizzazione (chi parla)…", step, n_steps)
        with tel.step("diarize") as o:
            from .transcription.diarize import ENGINE, assign_speakers, diarize
            segments, n_speakers = diarize(cfg.video)
            assign_speakers(manifest["shots"], segments)
            manifest["n_speakers"] = n_speakers
            o["engine"] = ENGINE
            o["n_speakers"] = n_speakers
            o["n_segments"] = len(segments)
            o["n_shots_with_speaker"] = sum(1 for s in manifest["shots"] if s.get("speakers"))
        log.info("  %s parlanti, %d turni di parola", n_speakers, len(segments))

    if cfg.vlm:
        step += 1
        log.info("[%d/%d] Descrizione visiva (%s)…", step, n_steps, cfg.vlm_model)
        with tel.step("vlm") as o:
            write_manifest(manifest, manifest_path)  # persisti prima del VLM (resume)
            from .captioning.caption import MlxVlmCaptioner, caption_manifest
            before = sum(1 for s in manifest["shots"] if s.get("description"))
            captioner = MlxVlmCaptioner(cfg.vlm_model)
            caption_manifest(manifest, cfg.video, captioner, n_frames=cfg.vlm_frames,
                             manifest_path=manifest_path)
            after = sum(1 for s in manifest["shots"] if s.get("description"))
            o["described"] = after - before
            o["total_described"] = after
            o["model"] = cfg.vlm_model
            o["vlm_frames"] = cfg.vlm_frames
        log.info("  %d descrizioni nuove, %d shot su %d descritti",
                 o["described"], o["total_described"], len(scenes))

    log.info("[%d/%d] Manifest + UI", n_steps, n_steps)
    with tel.step("manifest") as o:
        write_manifest(manifest, manifest_path)
        from .catalog.ui import build_html
        (out_dir / "index.html").write_text(build_html(manifest), encoding="utf-8")
        o["manifest"] = str(manifest_path)
        o["index_html"] = str(out_dir / "index.html")
    log.info("  → %s/  (manifest.json, index.html)", out_dir)

    from .catalog.gallery import write_gallery
    gallery_path, n_films = write_gallery(cfg.output_dir)
    log.info("  → %s  (galleria: %d film)", gallery_path, n_films)
    tel.close()
