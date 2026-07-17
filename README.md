# Scene Detector

Suddivide un film in clip (scene) tramite **shot boundary detection**. Rileva i tagli tra
inquadrature e ritaglia ogni scena in un file video separato.

Tre detector dietro un'interfaccia comune, intercambiabili:

| Detector | `-d` | Tipo | Device | Pesi | Uso |
|---|---|---|---|---|---|
| **TransNetV2** | `transnet` | neurale (default) | MPS/GPU | richiesti | primario, robusto anche su dissolvenze |
| **PySceneDetect** | `pyscenedetect` | classico (content-based) | CPU | nessuno | baseline veloce, ottimo su hard-cut |
| **AutoShot** | `autoshot` | neurale (NAS) | CPU | richiesti | seconda opinione / cross-check |
| **Ensemble** | `--ensemble` | TransNet + AutoShot | MPS+CPU | entrambi | agreement = confidenza, disaccordo = flag |

---

## Requisiti

- **Python ≥ 3.10** (testato su 3.13)
- **ffmpeg / ffprobe** nel PATH (`brew install ffmpeg`)

## Installazione

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .              # base: scenedetect, numpy, typer
pip install -e '.[neural]'    # per TransNetV2 / AutoShot: torch, pillow, einops
pip install -e '.[faces]'     # riconoscimento personaggi: insightface, onnxruntime (CoreML)
```

## Uso

### «Fa tutto» — un comando

```bash
scene-detector "FILM.mp4" --all -o catalogo/
```

`--all` esegue l'intera pipeline: **rilevamento shot → taglio clip → riconoscimento personaggi →
trascrizione dialoghi (ASR) → descrizione visiva per shot (VLM) → manifest + UI**. I pesi neurali sono presi **in automatico**
da `weights/transnetv2.pth` (e `weights/autoshot.pth`) se presenti — lancialo dalla cartella del
progetto, oppure passa i path.

Output in `catalogo/<nome-film>/`: `scene-NNN.mp4`, `manifest.json`, `index.html` (apri quest'ultimo).
Le fasi `[1/N]…[N/N]` con barre mostrano l'avanzamento.

> La **descrizione visiva** per shot (VLM) è locale su Apple Silicon (`mlx-vlm` + Qwen2.5-VL-3B 4-bit).
> È lo step più lungo (~5s/shot); è **resumable**: un run interrotto riparte saltando gli shot già
> descritti. Installa con `pip install -e '.[vlm]'`; il modello si scarica al primo uso (~2 GB).
>
> Il **riconoscimento personaggi** (`--faces`) rileva i volti (InsightFace SCRFD+ArcFace su CoreML)
> e li clusterizza in personaggi ricorrenti sull'intero film. Con `--faces-gallery <dir>` (una
> sotto-cartella `<Nome>/` con foto per personaggio) li etichetta coi nomi reali; senza gallery
> restano "Personaggio N" da **rinominare nella UI**. I personaggi presenti in ogni shot arricchiscono
> il prompt del VLM (descrizioni nominate). Resumable; `pip install -e '.[faces]'`, `buffalo_l` ~300 MB
> al primo uso. Le foto della gallery devono mostrare il volto **con un minimo di contesto** (non crop nudi).

### Esempi per singolo job

```bash
# solo segmentazione, baseline classica (nessun peso)
scene-detector FILM.mp4 -d pyscenedetect -o clips/

# segmentazione neurale (default); pesi auto da weights/ o espliciti
scene-detector FILM.mp4 -d transnet -o clips/

# ensemble TransNet + AutoShot (flag sui boundary in disaccordo)
scene-detector FILM.mp4 --ensemble -o clips/

# tutto, ASR su tutti i core, lingua forzata, taglio veloce
scene-detector FILM.mp4 --all --asr-model large-v3-turbo --asr-lang it --split-mode copy -o catalogo/

# tutto con un modello ASR più leggero
scene-detector FILM.mp4 --all --asr-model medium
```

### Tutte le opzioni

| Flag | Default | Descrizione |
|---|---|---|
| `VIDEO` | — | film in ingresso (argomento posizionale) |
| `--all` | off | pipeline completa: detection + split + ASR (+ VLM quando disponibile) |
| `-o, --output-dir` | `clips` | cartella radice; l'output va in `<dir>/<nome-film>/` |
| `-d, --detector` | `transnet` | `transnet` \| `autoshot` \| `pyscenedetect` |
| `--ensemble` | off | TransNet + AutoShot con riconciliazione + flag disaccordi |
| `--transnet-weights` | `weights/transnetv2.pth` se c'è | pesi TransNetV2 |
| `--autoshot-weights` | `weights/autoshot.pth` se c'è | pesi AutoShot |
| `--split-mode` | `copy` | `copy` (veloce, snap keyframe) \| `reencode` (frame-accurate, lento) |
| `--threshold` | `0.5` | soglia boundary neurale |
| `--min-scene-len` | `15` | frame minimi per shot |
| `--asr` | off | trascrivi i dialoghi (faster-whisper) |
| `--asr-model` | `large-v3-turbo` | `tiny/base/small/medium/large-v3/large-v3-turbo` o path |
| `--asr-lang` | auto | lingua ISO (es. `it`) |
| `--asr-threads` | `0` | thread CPU per l'ASR (0 = tutti i core) |
| `--vlm` | off | descrizione visiva per shot (mlx-vlm, Apple Silicon) |
| `--vlm-model` | `Qwen2.5-VL-3B-Instruct-4bit` | repo `mlx-community` o path locale |
| `--vlm-frames` | `3` | frame campionati per shot (inizio/metà/fine) |
| `--faces` | off | riconoscimento personaggi (InsightFace) per arricchire il VLM |
| `--faces-gallery` | — | cartella `<Nome>/*.jpg` per etichettare i personaggi (opz.) |
| `--faces-frames` | `6` | frame campionati per shot per il riconoscimento volti |
| `--faces-threshold` | `0.5` | soglia coseno per clustering / match gallery |
| `--faces-min-score` | `0.5` | soglia `det_score`: scarta i volti deboli |

### Film intero (~3.5h) — consigli

- `--split-mode copy` (default): `reencode` su migliaia di clip = ore.
- ASR: `large-v3-turbo` + `--asr-threads 0` + VAD (attivo) → ~30-60 min. Job lungo (~1.5-2h): lascialo girare.
- Spazio disco: migliaia di clip ≈ dimensione del film.

## Pesi

I pesi non sono nel repo (`weights/` è in `.gitignore`).

### TransNetV2 — `weights/transnetv2.pth`

Convertiti dai pesi TensorFlow ufficiali. TF serve **solo** alla conversione (una-tantum);
il runtime usa solo torch. Ricetta:

```bash
git clone --depth 1 https://github.com/soCzech/TransNetV2.git
python3.13 -m venv .venv_convert && .venv_convert/bin/pip install tensorflow torch numpy
cd TransNetV2/inference-pytorch
../../.venv_convert/bin/python convert_weights.py --tf_weights ../inference/transnetv2-weights/ --test
# --test verifica parita torch vs TF (atteso 100% match)
# -> transnetv2-pytorch-weights.pth   (copia in ../../weights/transnetv2.pth)
```

### AutoShot — `weights/autoshot.pth`

Scarica `ckpt_0_200_0.pth` dal repo ufficiale [wentaozhu/AutoShot](https://github.com/wentaozhu/AutoShot)
(link **Baidu**, passcode `sfkq`) e copialo in `weights/autoshot.pth`. Non esiste mirror diretto;
l'unica fonte è Baidu.

## Valutazione (F1)

Modulo `scene_detector.evaluation.eval` per confrontare le scene predette con un ground-truth
(file con `start end` per riga, in frame):

```python
from scene_detector.evaluation.eval import evaluate, read_scenes_txt
gt = read_scenes_txt("gt.txt")
metrics = evaluate(pred_scenes, gt, tol=5)   # {precision, recall, f1, tp, fp, fn}
```

## Note & gotcha

- **AutoShot gira su CPU**: la sua `ColorHistograms` usa op intere (bit-shift/segment-sum)
  non supportate da MPS. TransNetV2 gira su MPS.
- **Taglio**: `copy` è veloce ma taglia sui keyframe (±GOP); `reencode` è frame-accurate ma lento.
- **Memoria**: i frame (48×27) sono caricati interi in RAM (~1.25 GB per un film di 2h @24fps).
- **Output per film**: più film sulla stessa `-o` non si mescolano (ognuno in `<nome-film>/`).

## Test

```bash
python -m pytest tests/        # oppure il runner manuale se pytest non e' installato
```

## Struttura

Package per stadio della pipeline:

```
scene_detector/
  cli.py                    # entrypoint typer (parse flag -> pipeline)
  pipeline.py               # orchestrazione degli step (detection -> ... -> galleria)
  core/
    config.py               # Config + enum DetectorKind / SplitMode
    scene.py                # datamodel Scene + builder + enforce_min_len
    cpu.py                  # resolve_workers
    telemetry.py            # osservabilità run (logs/run-<ts>/)
  io/video.py               # probe ffprobe -> VideoInfo
  detection/
    base.py                 # Protocol SceneDetector
    factory.py              # build_detector
    neural.py               # read_small_frames + probs_to_ranges
    pyscenedetect.py
    transnetv2.py
    autoshot.py
    confidence.py           # riconciliazione ensemble (agreement / flag)
    models/
      transnetv2.py         # architettura (vendor soCzech/TransNetV2, MIT)
      autoshot/             # architettura AutoShot (vendor wentaozhu/AutoShot) + einops
      wrapper.py            # TransNetV2Predictor / AutoShotPredictor (load + windowing)
  segmentation/splitter.py  # export clip via ffmpeg
  transcription/
    asr.py                  # faster-whisper
    align.py                # assegna dialoghi agli shot
  captioning/caption.py     # VLM: sample_frames + backend MLX + caption_manifest (resumable)
  recognition/
    faces.py                # InsightFace (SCRFD+ArcFace) + gallery + orchestratore
    identify.py             # clustering coseno + match gallery (logica pura)
  catalog/
    manifest.py             # manifest.json del catalogo shot
    ui.py                   # UI HTML per-film
    gallery.py              # galleria multi-film (index.html)
  evaluation/eval.py        # F1 / precision / recall su boundary
```

## Crediti

- [TransNetV2](https://github.com/soCzech/TransNetV2) — Souček & Lokoč (MIT)
- [AutoShot](https://github.com/wentaozhu/AutoShot) — Zhu et al., CVPR-W 2023
- [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) — Castellano (BSD-3)
