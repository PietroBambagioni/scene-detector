from __future__ import annotations

from .core import telemetry as tel_mod
from .core.config import Config, DetectorKind
from .core.cpu import resolve_workers
from .core.scene import enforce_min_len
from .core.telemetry import log
from .detection import build_detector
from .detection import confidence as conf_mod
from .detection.neural import read_small_frames
from .io.video import probe
from .segmentation.splitter import split


def run(cfg: Config) -> None:
    """Orchestrazione end-to-end: detection → split → (faces) → (ASR) → (VLM) → manifest/UI → galleria.

    Tutti i parametri del run vivono in `cfg` (`cli` lo popola dai flag Typer).
    """
    video = cfg.video
    output_dir = cfg.output_dir
    detector = cfg.detector
    ensemble = cfg.ensemble
    split_mode = cfg.split_mode
    threshold = cfg.threshold
    min_scene_len = cfg.min_scene_len
    low_mem = cfg.low_mem
    transnet_weights = cfg.transnet_weights
    autoshot_weights = cfg.autoshot_weights
    jobs = cfg.jobs
    asr, asr_model, asr_lang, asr_threads = cfg.asr, cfg.asr_model, cfg.asr_lang, cfg.asr_threads
    vlm, vlm_model, vlm_frames = cfg.vlm, cfg.vlm_model, cfg.vlm_frames
    faces, faces_gallery, faces_frames = cfg.faces, cfg.faces_gallery, cfg.faces_frames
    faces_threshold, faces_min_score = cfg.faces_threshold, cfg.faces_min_score

    info = probe(video)
    out_dir = output_dir / video.stem

    tel = tel_mod.Telemetry(out_dir)
    log.info("[probe] %d frame @ %.3f fps, %.1fs", info.n_frames, info.fps, info.duration)

    split_workers = resolve_workers(jobs)
    asr_workers = resolve_workers(asr_threads) if asr else None
    env = tel_mod.collect_env()
    tel.write_config({
        "command": tel_mod.command_snapshot(),
        "flags": {
            "detector": detector.value, "ensemble": ensemble,
            "split_mode": split_mode.value, "threshold": threshold,
            "min_scene_len": min_scene_len, "low_mem": low_mem,
            "asr": asr, "asr_model": asr_model, "asr_lang": asr_lang, "asr_threads": asr_threads,
            "vlm": vlm, "vlm_model": vlm_model, "vlm_frames": vlm_frames,
            "faces": faces, "faces_gallery": str(faces_gallery) if faces_gallery else None,
            "faces_frames": faces_frames, "faces_threshold": faces_threshold,
            "faces_min_score": faces_min_score,
            "jobs": jobs, "output_dir": str(output_dir),
            "transnet_weights": str(transnet_weights) if transnet_weights else None,
            "autoshot_weights": str(autoshot_weights) if autoshot_weights else None,
        },
        "mode": {
            "detector": "ensemble" if ensemble else detector.value,
            "split_mode": split_mode.value,
            "device": "mps" if env.get("mps_available") else "cpu",
            "split_workers": split_workers, "asr_workers": asr_workers,
        },
        "video": {
            "name": video.name, "fps": info.fps, "n_frames": info.n_frames,
            "duration": info.duration, "width": info.width, "height": info.height,
        },
        "env": env,
    })

    n_steps = 3 + (1 if faces else 0) + (1 if asr else 0) + (1 if vlm else 0)

    log.info("[1/%d] Rilevamento shot…", n_steps)
    with tel.step("detection") as o:
        if ensemble:
            t_det = build_detector(DetectorKind.transnet, cfg)
            a_det = build_detector(DetectorKind.autoshot, cfg)
            assert t_det.input_size == a_det.input_size, "ensemble: input dei due detector diverso"
            if low_mem:
                a = t_det.detect(info)  # streaming: decodifica indipendente (RAM bounded)
                b = a_det.detect(info)
            else:
                h, w = t_det.input_size  # (H, W) — decodifica condivisa una sola volta
                frames = read_small_frames(info.path, w, h, total=info.n_frames, desc="[decode] frames")
                a = t_det.detect_from_frames(frames, info)
                b = a_det.detect_from_frames(frames, info)
            scenes, flags = conf_mod.reconcile(a, b, info.n_frames, info.fps, t_det.probs, cfg.agreement_tol)
            if flags:
                log.info("  %d boundary in disaccordo (rivedere): %s", len(flags), flags)
            o["n_flag"] = len(flags)
            o["flags"] = list(flags)
        else:
            scenes = build_detector(detector, cfg).detect(info)
        scenes = enforce_min_len(scenes, cfg.min_scene_len)
        o["n_shots"] = len(scenes)
        o["threshold"] = threshold
    log.info("  %d shot", len(scenes))

    log.info("[2/%d] Taglio %d clip…", n_steps, len(scenes))
    with tel.step("split") as o:
        split(info, scenes, out_dir, split_mode, jobs=jobs)
        o["n_clips"] = len(scenes)
        o["split_mode"] = split_mode.value
        o["workers"] = split_workers

    from .catalog.manifest import build_manifest, write_manifest
    label = "ensemble" if ensemble else detector.value
    manifest = build_manifest(info, scenes, label)
    manifest_path = out_dir / "manifest.json"
    step = 2

    if faces:
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
                recognizer = FaceRecognizer(min_score=faces_min_score)
                gallery = load_gallery(faces_gallery, recognizer) if faces_gallery else None
                n_faces, n_chars = recognize_characters(
                    manifest, video, recognizer, gallery=gallery, n_frames=faces_frames,
                    threshold=faces_threshold, film_dir=out_dir,
                )
            o["n_faces"] = n_faces
            o["n_characters"] = n_chars
            o["gallery"] = str(faces_gallery) if faces_gallery else None
        log.info("  %d volti → %d personaggi", n_faces, n_chars)

    if asr:
        step += 1
        log.info("[%d/%d] Trascrizione dialoghi (%s)…", step, n_steps, asr_model)
        with tel.step("asr") as o:
            from .transcription.asr import transcribe
            from .transcription.align import assign_dialogue
            segments, lang = transcribe(video, asr_model, language=asr_lang, cpu_threads=asr_threads)
            assign_dialogue(manifest["shots"], segments)
            o["language"] = lang
            o["n_segments"] = len(segments)
            o["n_shots_with_dialogue"] = sum(1 for s in manifest["shots"] if s.get("dialogue"))
            o["model"] = asr_model
            o["threads"] = asr_workers
        log.info("  lingua=%s, %d segmenti", lang, len(segments))

    if vlm:
        step += 1
        log.info("[%d/%d] Descrizione visiva (%s)…", step, n_steps, vlm_model)
        with tel.step("vlm") as o:
            write_manifest(manifest, manifest_path)  # persisti prima del VLM (resume)
            from .captioning.caption import MlxVlmCaptioner, caption_manifest
            before = sum(1 for s in manifest["shots"] if s.get("description"))
            captioner = MlxVlmCaptioner(vlm_model)
            caption_manifest(manifest, video, captioner, n_frames=vlm_frames, manifest_path=manifest_path)
            after = sum(1 for s in manifest["shots"] if s.get("description"))
            o["described"] = after - before
            o["total_described"] = after
            o["model"] = vlm_model
            o["vlm_frames"] = vlm_frames

    log.info("[%d/%d] Manifest + UI", n_steps, n_steps)
    with tel.step("manifest") as o:
        write_manifest(manifest, manifest_path)
        from .catalog.ui import build_html
        (out_dir / "index.html").write_text(build_html(manifest), encoding="utf-8")
        o["manifest"] = str(manifest_path)
        o["index_html"] = str(out_dir / "index.html")
    log.info("  → %s/  (manifest.json, index.html)", out_dir)

    from .catalog.gallery import write_gallery
    gallery_path, n_films = write_gallery(output_dir)
    log.info("  → %s  (galleria: %d film)", gallery_path, n_films)
    tel.close()
