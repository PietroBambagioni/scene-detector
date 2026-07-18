# Scene Detector — Panoramica

## Cosa fa

Prende un film e lo **suddivide automaticamente in clip (scene)** rilevando i tagli tra
inquadrature (*shot boundary detection*). Da un singolo comando produce un catalogo navigabile:
ogni scena diventa un file video separato, arricchito con **personaggi riconosciuti**,
**dialoghi trascritti** e **descrizione visiva** dello shot, il tutto raccolto in un
`manifest.json` + `index.html`.

```bash
scene-detector "FILM.mp4" --all -o catalogo/
```

Pipeline `--all`: **rilevamento shot → taglio clip → riconoscimento personaggi →
trascrizione dialoghi (ASR) → descrizione visiva per shot (VLM) → manifest + UI**.

## Modelli e tecnologie

### Shot boundary detection
| Modello | Tipo | Device | Ruolo |
|---|---|---|---|
| **TransNetV2** (soCzech, MIT) | neurale, CNN 3D | MPS/GPU | primario, robusto anche su dissolvenze |
| **AutoShot** (Zhu et al., CVPR-W 2023) | neurale, NAS | CPU | seconda opinione / cross-check |
| **PySceneDetect** (Castellano, BSD-3) | classico content-based | CPU | baseline veloce su hard-cut |
| **Ensemble** | TransNet + AutoShot | MPS+CPU | agreement = confidenza, disaccordo = flag |

### Arricchimento del catalogo
- **Riconoscimento personaggi** — [InsightFace](https://github.com/deepinsight/insightface):
  **SCRFD** (detection volti) + **ArcFace** (embedding) via modello `buffalo_l`, runtime
  **ONNX Runtime / CoreML**. Clustering coseno dei volti sull'intero film; gallery opzionale
  per etichettare coi nomi reali.
- **Trascrizione dialoghi (ASR)** — [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
  (Whisper via CTranslate2), default `large-v3-turbo`, con VAD; i segmenti vengono allineati agli shot.
- **Descrizione visiva (VLM)** — [mlx-vlm](https://github.com/Blaizzy/mlx-vlm) su Apple Silicon,
  modello **Qwen2.5-VL-3B-Instruct-4bit**. Campiona alcuni frame per shot e genera una descrizione;
  step resumable. I personaggi riconosciuti arricchiscono il prompt (descrizioni nominate).

### Stack di base
- **Python ≥ 3.10** (testato su 3.13)
- **Typer** — CLI
- **PyTorch** — inference dei modelli neurali (TransNetV2 / AutoShot), `einops` per il windowing
- **NumPy / OpenCV** (via `scenedetect`) — elaborazione frame
- **ffmpeg / ffprobe** — probe video e taglio/export delle clip (`copy` veloce o `reencode` frame-accurate)
- **psutil** — telemetria run (CPU% / RSS live)
- **pytest** — test

## Struttura (per stadio della pipeline)

```
scene_detector/
  cli.py / pipeline.py      # entrypoint + orchestrazione step
  core/                     # Config, datamodel Scene, workers, telemetria
  io/video.py               # probe ffprobe -> VideoInfo
  detection/                # detector (transnet/autoshot/pyscenedetect) + ensemble + modelli vendored
  segmentation/splitter.py  # export clip via ffmpeg
  transcription/            # ASR (faster-whisper) + allineamento agli shot
  captioning/caption.py     # VLM (MLX) resumable
  recognition/              # InsightFace + clustering + gallery
  catalog/                  # manifest.json + UI HTML per-film + galleria multi-film
  evaluation/eval.py        # F1 / precision / recall sui boundary
```

## Crediti modelli
- [TransNetV2](https://github.com/soCzech/TransNetV2) — Souček & Lokoč (MIT)
- [AutoShot](https://github.com/wentaozhu/AutoShot) — Zhu et al., CVPR-W 2023
- [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) — Castellano (BSD-3)
- [InsightFace](https://github.com/deepinsight/insightface) — SCRFD + ArcFace (`buffalo_l`)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Whisper / CTranslate2
- [Qwen2.5-VL](https://github.com/QwenLM/Qwen2.5-VL) — VLM via [mlx-vlm](https://github.com/Blaizzy/mlx-vlm)
</content>
</invoke>
