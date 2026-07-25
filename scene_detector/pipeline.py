from __future__ import annotations

import os
from pathlib import Path

from .core import telemetry as tel_mod
from .core.config import Config, SplitMode
from .core.cpu import resolve_workers
from .core.scene import enforce_min_len
from .core.telemetry import log
from .detection import build_detector
from .io.video import probe
from .segmentation.splitter import split


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
        "flags": {
            "detector": cfg.detector.value,
            "split_mode": cfg.split_mode.value, "threshold": cfg.threshold,
            "min_scene_len": cfg.min_scene_len,
            "asr": cfg.asr, "asr_model": cfg.asr_model, "asr_lang": cfg.asr_lang,
            "asr_threads": cfg.asr_threads,
            "vlm": cfg.vlm, "vlm_model": cfg.vlm_model, "vlm_frames": cfg.vlm_frames,
            "faces": cfg.faces,
            "faces_gallery": str(cfg.faces_gallery) if cfg.faces_gallery else None,
            "faces_frames": cfg.faces_frames, "faces_threshold": cfg.faces_threshold,
            "faces_min_score": cfg.faces_min_score,
            "jobs": cfg.jobs, "output_dir": str(cfg.output_dir),
            "transnet_weights": str(cfg.transnet_weights) if cfg.transnet_weights else None,
        },
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

    n_steps = 3 + (1 if cfg.faces else 0) + (1 if cfg.asr else 0) + (1 if cfg.vlm else 0)

    log.info("[1/%d] Rilevamento shot…", n_steps)
    with tel.step("detection") as o:
        scenes = build_detector(cfg.detector, cfg).detect(info)
        scenes = enforce_min_len(scenes, cfg.min_scene_len)
        o["n_shots"] = len(scenes)
        o["threshold"] = cfg.threshold
    log.info("  %d shot", len(scenes))

    cutting = cfg.split_mode is not SplitMode.none
    with tel.step("split") as o:
        if cutting:
            log.info("[2/%d] Taglio %d clip…", n_steps, len(scenes))
            split(info, scenes, out_dir, cfg.split_mode, jobs=cfg.jobs)
            o["n_clips"] = len(scenes)
        else:
            log.info("[2/%d] Taglio saltato (--split-mode none): la UI usa i media fragments",
                     n_steps)
            o["n_clips"] = 0
        o["split_mode"] = cfg.split_mode.value
        o["workers"] = split_workers

    from .catalog.manifest import build_manifest, write_manifest
    label = cfg.detector.value
    # senza clip la UI riproduce il film originale a intervalli: le serve come raggiungerlo
    # dalla cartella del catalogo (relativo: catalogo e film restano spostabili insieme)
    video_src = None if cutting else os.path.relpath(Path(cfg.video).resolve(), out_dir.resolve())
    manifest = build_manifest(info, scenes, label,
                              clip_template=None if not cutting else "scene-{:03d}.mp4",
                              video_src=video_src)
    manifest_path = out_dir / "manifest.json"
    step = 2

    if cfg.faces:
        step += 1
        log.info("[%d/%d] Riconoscimento personaggi…", step, n_steps)
        with tel.step("faces") as o:
            from .catalog.manifest import load_manifest
            prior = load_manifest(manifest_path) if manifest_path.exists() else None
            if prior and prior.get("cast"):
                manifest["cast"] = prior["cast"]  # resume: riusa il cast già calcolato (+ eventuali rinomine)
                prior_chars = {s["index"]: s.get("characters", []) for s in prior["shots"]}
                for s in manifest["shots"]:
                    s["characters"] = prior_chars.get(s["index"], [])
                n_faces, n_chars = 0, len(manifest["cast"])
            else:
                write_manifest(manifest, manifest_path)  # persisti prima (crash-safe)
                from .recognition import FaceRecognizer, load_gallery, recognize_characters
                recognizer = FaceRecognizer(min_score=cfg.faces_min_score)
                gallery = load_gallery(cfg.faces_gallery, recognizer) if cfg.faces_gallery else None
                n_faces, n_chars = recognize_characters(
                    manifest, cfg.video, recognizer, gallery=gallery, n_frames=cfg.faces_frames,
                    threshold=cfg.faces_threshold, min_shots=cfg.faces_min_shots,
                    min_face_px=cfg.faces_min_px, film_dir=out_dir,
                )
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
