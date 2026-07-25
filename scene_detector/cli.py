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
    split_mode: SplitMode = typer.Option(SplitMode.copy, "--split-mode"),
    threshold: float = typer.Option(0.05, "--threshold",
                                    help="Soglia boundary neurale (0,05: vedi core/config.py)"),
    min_scene_len: int = typer.Option(5, "--min-scene-len",
                                      help="Frame minimi per shot (5: vedi core/config.py)"),
    transnet_weights: Path = typer.Option(None, "--transnet-weights"),
    asr: bool = typer.Option(False, "--asr", help="Trascrivi i dialoghi (faster-whisper)"),
    asr_model: str = typer.Option("large-v3-turbo", "--asr-model",
                                  help="Modello Whisper: tiny/base/small/medium/large-v3/large-v3-turbo o path"),
    asr_lang: str = typer.Option(None, "--asr-lang", help="Lingua ISO (es. it); default auto"),
    asr_threads: int = typer.Option(0, "--asr-threads", help="Thread CPU per l'ASR (0 = auto: tutti i core meno 2)"),
    vlm: bool = typer.Option(False, "--vlm", help="Descrizione visiva per shot (mlx-vlm)"),
    vlm_model: str = typer.Option("mlx-community/Qwen3-VL-8B-Instruct-4bit", "--vlm-model",
                                  help="Modello VLM (repo mlx-community o path locale)"),
    vlm_frames: int = typer.Option(3, "--vlm-frames", help="Frame campionati per shot"),
    faces: bool = typer.Option(False, "--faces", help="Riconoscimento personaggi (InsightFace) per arricchire il VLM"),
    faces_gallery: Path = typer.Option(None, "--faces-gallery",
                                       help="Cartella <Nome>/*.jpg per etichettare i personaggi (opz.; senza, restano anonimi)"),
    faces_frames: int = typer.Option(6, "--faces-frames", help="Frame campionati per shot per il riconoscimento volti"),
    faces_threshold: float = typer.Option(0.5, "--faces-threshold", help="Soglia coseno per clustering/gallery volti"),
    faces_min_score: float = typer.Option(0.5, "--faces-min-score", help="Soglia det_score: scarta i volti deboli"),
    faces_min_px: int = typer.Option(50, "--faces-min-px", help="Lato minimo del volto in pixel: sotto, l'embedding è rumore"),
    faces_min_shots: int = typer.Option(3, "--faces-min-shots", help="Un personaggio entra nel cast se ricorre in >=N shot distinti (taglia le comparse)"),
    run_all: bool = typer.Option(False, "--all", help="Fa tutto: detection + split + faces + ASR + VLM"),
    max_detail: bool = typer.Option(False, "--max", help="Massimo dettaglio + multi-core: --all + reencode frame-accurate + multi-core (2 core liberi)"),
    jobs: int = typer.Option(0, "-j", "--jobs", help="Processi ffmpeg paralleli per il taglio (0 = auto: tutti i core meno 2)"),
):
    if max_detail:
        run_all = True
        split_mode = SplitMode.reencode
    if run_all:
        asr = True
        vlm = True
        faces = True
    if transnet_weights is None and Path("weights/transnetv2.pth").exists():
        transnet_weights = Path("weights/transnetv2.pth")

    cfg = Config(
        video=video, output_dir=output_dir, detector=detector,
        split_mode=split_mode, threshold=threshold, min_scene_len=min_scene_len,
        transnet_weights=transnet_weights,
        asr=asr, asr_model=asr_model, asr_lang=asr_lang, asr_threads=asr_threads,
        vlm=vlm, vlm_model=vlm_model, vlm_frames=vlm_frames,
        faces=faces, faces_gallery=faces_gallery, faces_frames=faces_frames,
        faces_threshold=faces_threshold, faces_min_score=faces_min_score,
        faces_min_px=faces_min_px, faces_min_shots=faces_min_shots,
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


setup_app = typer.Typer(add_completion=False, help="Scarica pesi e modelli: prepara il progetto.")


@setup_app.command()
def setup(
    weights_dir: Path = typer.Option(Path("weights"), "--weights-dir", "-w"),
    force: bool = typer.Option(False, "--force", help="Riscarica anche i pesi già presenti"),
    models: bool = typer.Option(False, "--models",
                                help="Scarica anche i modelli grandi (Whisper, VLM, volti): ~4 GB"),
):
    """Scarica i pesi neurali e verifica gli eseguibili esterni.

    Il peso di TransNetV2 (30 MB) arriva da un mirror con sha256 verificato.
    I modelli grandi si scaricano da soli al primo uso: `--models` li anticipa qui.
    """
    from .core.weights import REGISTRY, fetch, missing_tools

    missing = missing_tools()
    if missing:
        typer.secho(f"⚠  manca nel PATH: {', '.join(missing)}  →  brew install ffmpeg",
                    fg=typer.colors.YELLOW)

    for name in REGISTRY:
        def progress(n, done, total, _last=[-1]):
            pct = 100 * done // total if total else 0
            if pct != _last[0]:
                _last[0] = pct
                typer.echo(f"\r  {n}: {pct}%", nl=False)
        path = fetch(name, weights_dir, force=force, on_progress=progress)
        typer.echo(f"\r→ {name}: {path}" + " " * 12)

    if models:
        _fetch_big_models()
    typer.echo("Pronto." if not missing else "Pronto, ma installa prima ffmpeg.")


def _fetch_big_models(asr_model="large-v3-turbo",
                      vlm_model="mlx-community/Qwen3-VL-8B-Instruct-4bit"):
    """Anticipa il download dei modelli che altrimenti arrivano al primo run.

    Ognuno vive in un extra diverso: se l'extra non è installato lo si segnala e si prosegue,
    perché `--asr` senza `--vlm` (o viceversa) è un uso legittimo.
    """
    steps = [
        ("ASR", "'.[asr]'", lambda: __import__("faster_whisper").WhisperModel(asr_model, device="cpu")),
        ("VLM", "'.[vlm]'", lambda: __import__("mlx_vlm").load(vlm_model)),
        ("volti", "'.[faces]'", lambda: __import__("insightface").app.FaceAnalysis(name="buffalo_l").prepare(ctx_id=-1)),
    ]
    for label, extra, load in steps:
        typer.echo(f"→ {label}…")
        try:
            load()
        except ImportError:
            typer.secho(f"   saltato: manca l'extra, `pip install -e {extra}`", fg=typer.colors.YELLOW)


bench_app = typer.Typer(add_completion=False, help="Valuta il detector su un ground truth pubblico.")


@bench_app.command()
def benchmark(
    data_dir: Path = typer.Option(Path("prove/shot-dataset"), "--data-dir",
                                  help="Dove tenere ground truth e video scaricati"),
    limit: int = typer.Option(50, "--limit", help="Quanti video di test usare (0 = tutti i 200)"),
    tol: int = typer.Option(5, "--tol", help="Tolleranza in frame per il match sui boundary"),
    min_iou: float = typer.Option(0.5, "--min-iou", help="IoU minimo perché una transizione sia un TP"),
):
    """Scarica il test set di SHOT (200 video annotati) e ci misura il detector.

    Niente annotazione a mano: il ground truth è pubblico e arriva dal mirror HF da cui
    prendiamo già i pesi. Dei ~20 GB di archivi scarica **solo** i video del test set, letti
    dagli zip remoti via range HTTP.
    """
    from .core.weights import missing_tools
    from .evaluation import benchmark as bench
    from .evaluation.shot_dataset import fetch_ground_truth, fetch_videos

    if missing_tools():
        typer.secho("⚠  serve ffmpeg/ffprobe nel PATH", fg=typer.colors.YELLOW)
        raise typer.Exit(1)

    gt = fetch_ground_truth(data_dir)
    typer.echo(f"ground truth: {len(gt)} video, {sum(len(v) for v in gt.values())} shot")

    videos = fetch_videos(gt, data_dir / "videos", limit=limit or None,
                          on_progress=lambda v, n, tot: typer.echo(f"\r  scaricati {n}/{tot or len(gt)}",
                                                                   nl=False))
    typer.echo(f"\rvideo pronti: {len(videos)}" + " " * 20)

    cfg = Config(video=Path("."),
                 transnet_weights=Path("weights/transnetv2.pth"))
    with typer.progressbar(length=len(videos), label="[bench]") as bar:
        res = bench.run(videos, gt, cfg, tol=tol, min_iou=min_iou,
                        on_video=lambda *a: bar.update(1))

    b, t = res["boundary"], res["transition"]
    typer.echo(f"\n{res['n_videos']} video · detector: transnet")
    typer.echo(f"boundary   (tol {res['tol']})  P {b['precision']:.3f}  R {b['recall']:.3f}  "
               f"F1 {b['f1']:.3f}   tp {b['tp']} fp {b['fp']} fn {b['fn']}")
    typer.echo(f"transizioni (IoU>={res['min_iou']})  P {t['precision']:.3f}  R {t['recall']:.3f}  "
               f"F1 {t['f1']:.3f}   mean IoU {t['mean_iou']:.3f}")
    typer.echo(f"  ({res['n_gt_graduali']} transizioni graduali nel ground truth di questi video)")


if __name__ == "__main__":
    app()
