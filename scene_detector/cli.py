from __future__ import annotations

from pathlib import Path

import typer

from . import confidence as conf_mod
from . import telemetry as tel_mod
from .config import Config, DetectorKind, SplitMode
from .cpu import resolve_workers
from .detectors import build_detector
from .detectors._neural import read_small_frames
from .io.video import probe
from .scene import enforce_min_len
from .splitter import split
from .telemetry import log

app = typer.Typer(add_completion=False, help="Suddivide un film in clip (scene).")


@app.command()
def run(
    video: Path = typer.Argument(..., exists=True, dir_okay=False, help="Film in ingresso"),
    output_dir: Path = typer.Option(Path("clips"), "--output-dir", "-o"),
    detector: DetectorKind = typer.Option(DetectorKind.transnet, "--detector", "-d"),
    ensemble: bool = typer.Option(False, "--ensemble", help="TransNet + AutoShot con confidence"),
    split_mode: SplitMode = typer.Option(SplitMode.copy, "--split-mode"),
    threshold: float = typer.Option(0.5, "--threshold"),
    min_scene_len: int = typer.Option(15, "--min-scene-len"),
    low_mem: bool = typer.Option(False, "--low-mem",
                                 help="Detection neurale in streaming: RAM da GB a MB "
                                      "(in ensemble decodifica due volte, niente decode-once)"),
    transnet_weights: Path = typer.Option(None, "--transnet-weights"),
    autoshot_weights: Path = typer.Option(None, "--autoshot-weights"),
    asr: bool = typer.Option(False, "--asr", help="Trascrivi i dialoghi (faster-whisper)"),
    asr_model: str = typer.Option("large-v3-turbo", "--asr-model",
                                  help="Modello Whisper: tiny/base/small/medium/large-v3/large-v3-turbo o path"),
    asr_lang: str = typer.Option(None, "--asr-lang", help="Lingua ISO (es. it); default auto"),
    asr_threads: int = typer.Option(0, "--asr-threads", help="Thread CPU per l'ASR (0 = auto: tutti i core meno 2)"),
    vlm: bool = typer.Option(False, "--vlm", help="Descrizione visiva per shot (mlx-vlm)"),
    vlm_model: str = typer.Option("mlx-community/Qwen2.5-VL-3B-Instruct-4bit", "--vlm-model",
                                  help="Modello VLM (repo mlx-community o path locale)"),
    vlm_frames: int = typer.Option(3, "--vlm-frames", help="Frame campionati per shot"),
    run_all: bool = typer.Option(False, "--all", help="Fa tutto: detection + split + ASR + VLM"),
    max_detail: bool = typer.Option(False, "--max", help="Massimo dettaglio + multi-core: --all + reencode frame-accurate + multi-core (2 core liberi)"),
    jobs: int = typer.Option(0, "-j", "--jobs", help="Processi ffmpeg paralleli per il taglio (0 = auto: tutti i core meno 2)"),
):
    if max_detail:
        run_all = True
        split_mode = SplitMode.reencode
    if run_all:
        asr = True
        vlm = True
    if transnet_weights is None and Path("weights/transnetv2.pth").exists():
        transnet_weights = Path("weights/transnetv2.pth")
    if autoshot_weights is None and Path("weights/autoshot.pth").exists():
        autoshot_weights = Path("weights/autoshot.pth")

    cfg = Config(
        video=video, output_dir=output_dir, detector=detector, ensemble=ensemble,
        split_mode=split_mode, threshold=threshold, min_scene_len=min_scene_len,
        low_mem=low_mem,
        transnet_weights=transnet_weights, autoshot_weights=autoshot_weights,
    )

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

    n_steps = 3 + (1 if asr else 0) + (1 if vlm else 0)

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
            scenes, flags = conf_mod.reconcile(a, b, info.n_frames, info.fps, cfg.agreement_tol)
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

    from .manifest import build_manifest, write_manifest
    label = "ensemble" if ensemble else detector.value
    manifest = build_manifest(info, scenes, label)
    manifest_path = out_dir / "manifest.json"
    step = 2

    if asr:
        step += 1
        log.info("[%d/%d] Trascrizione dialoghi (%s)…", step, n_steps, asr_model)
        with tel.step("asr") as o:
            from .asr import transcribe
            from .align import assign_dialogue
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
            from .caption import MlxVlmCaptioner, caption_manifest
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
        from .ui import build_html
        (out_dir / "index.html").write_text(build_html(manifest), encoding="utf-8")
        o["manifest"] = str(manifest_path)
        o["index_html"] = str(out_dir / "index.html")
    log.info("  → %s/  (manifest.json, index.html)", out_dir)

    from .gallery import write_gallery
    gallery_path, n_films = write_gallery(output_dir)
    log.info("  → %s  (galleria: %d film)", gallery_path, n_films)
    tel.close()


index_app = typer.Typer(add_completion=False, help="(Ri)genera la galleria dei cataloghi.")


@index_app.command()
def index(output_dir: Path = typer.Option(Path("clips"), "--output-dir", "-o",
                                          help="Cartella con i cataloghi per-film")):
    """(Ri)genera la galleria `<out>/index.html` scandendo i cataloghi presenti."""
    from .gallery import write_gallery
    gallery_path, n_films = write_gallery(output_dir)
    typer.echo(f"→ {gallery_path}  ({n_films} film)")


def main():
    app()


def main_index():
    index_app()


if __name__ == "__main__":
    main()
