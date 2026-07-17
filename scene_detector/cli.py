from __future__ import annotations

from pathlib import Path

import typer

from . import pipeline
from .core.config import Config, DetectorKind, SplitMode

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
        asr=asr, asr_model=asr_model, asr_lang=asr_lang, asr_threads=asr_threads,
        vlm=vlm, vlm_model=vlm_model, vlm_frames=vlm_frames,
        jobs=jobs,
    )

    pipeline.run(cfg)


index_app = typer.Typer(add_completion=False, help="(Ri)genera la galleria dei cataloghi.")


@index_app.command()
def index(output_dir: Path = typer.Option(Path("clips"), "--output-dir", "-o",
                                          help="Cartella con i cataloghi per-film")):
    """(Ri)genera la galleria `<out>/index.html` scandendo i cataloghi presenti."""
    from .catalog.gallery import write_gallery
    gallery_path, n_films = write_gallery(output_dir)
    typer.echo(f"→ {gallery_path}  ({n_films} film)")


def main():
    app()


def main_index():
    index_app()


if __name__ == "__main__":
    main()
