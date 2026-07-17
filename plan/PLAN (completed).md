# Scene Detector — Implementation Plan

## Obiettivo
Dato un film in ingresso, suddividerlo in clip (scene) esportate come file video, usando
**TransNetV2** come detector primario (shot boundary detection neurale) e **PySceneDetect**
come baseline veloce + motore di taglio ffmpeg. **AutoShot** opzionale come seconda opinione
neurale (ensemble / eval).

## Architettura (Opzione A)
TransNetV2 = verità di detection. PySceneDetect = baseline / cross-check + splitting.
Detector intercambiabili dietro un `Protocol` comune; lo splitter non conosce il detector.

```
film ─► TransNetV2 (boundary neurali)            [primario]
   │
   ├──► PySceneDetect (baseline + diff log)       [cross-check]
   │
   └──► [opz] AutoShot ──┐
                         ├─► confidence.reconcile ─► flag disaccordi   [ensemble]
         TransNetV2 ─────┘
                  ▼
         Scene[]   (frame ↔ timecode via fps)
                  ▼
         splitter ffmpeg ─► clips/film-scene-XXX.mp4
```

## Struttura
```
scene_detector/
  __init__.py
  cli.py                          # entrypoint typer
  config.py                       # Config dataclass + enum DetectorKind / SplitMode
  scene.py                        # datamodel Scene + builder + enforce_min_len
  io/
    video.py                      # probe ffprobe -> VideoInfo (fps, n_frames, durata)
  detectors/
    base.py                       # Protocol SceneDetector.detect(video) -> list[Scene]
    _neural.py                    # read_small_frames (ffmpeg 48x27) + probs_to_ranges
    pyscenedetect_detector.py     # REALE (ContentDetector / AdaptiveDetector)
    transnetv2_detector.py        # primario: wrapper + contratto modello (wiring = step 3)
    autoshot_detector.py          # [opz] wrapper + contratto modello (wiring = step 7)
  confidence.py                   # [opz] reconcile ensemble TransNet <-> AutoShot
  splitter.py                     # export clip via scenedetect.split_video_ffmpeg
tests/test_scene.py
pyproject.toml
```

## Data model
`Scene(index, start_frame, end_frame[incluso], fps, source, confidence)`.
Scene contigue: `next.start = prev.end + 1`. Timecode derivati da fps.

## Detector Protocol
`detect(video: VideoInfo) -> list[Scene]`.
Contratto modello neurale: `model.predict(uint8[N,27,48,3]) -> float[N]` (prob boundary/frame).
Frame estratti a 48×27 via pipe ffmpeg → RAM bassa anche su film lunghi.

## Step (con verifica)
1. Scaffold + deps                → `pip install -e .` ok, ffmpeg presente.        [FATTO]
2. `io/video.py` probe            → fps/n_frames/durata corretti su sample.
3. `transnetv2_detector` (wiring) → inference su sample, cut sensati.  **CRITICO / primario.**
4. `scene.py` + adapter           → round-trip frame↔timecode esatto.              [FATTO]
5. `splitter.py`                  → N clip, somma durate ≈ film, audio in sync.    [SCAFFOLD]
6. `pyscenedetect_detector`       → baseline + log diff vs TransNet.               [FATTO]
7. `autoshot_detector` (wiring)   → inference sample, confronto vs TransNet.       [OPZ]
8. `confidence.py`                → agreement=conf, disagreement=flag.  [OPZ, solo `--ensemble`] [SCAFFOLD]
9. `cli.py` + `config.py`         → end-to-end su clip corta.                      [SCAFFOLD]
10. Eval                          → F1 TransNet vs AutoShot vs ground-truth.       [OPZ]

Percorso minimo produttivo: 1→6, 9 (detector PySceneDetect già eseguibile). Step 7/8/10 opzionali.

## Config / flag
```
--detector {transnet|autoshot|pyscenedetect}   default: transnet
--ensemble                                      TransNet + AutoShot + confidence
--split-mode {copy|reencode}                    default: copy
--threshold FLOAT                               soglia boundary neurale (0.5)
--min-scene-len INT                             frame minimi per scena (15)
--transnet-weights PATH / --autoshot-weights PATH
--output-dir / -o
```

## Gotcha
- **Taglio**: `copy` veloce ma snap a keyframe (±GOP); `reencode` frame-accurate ma lento. Default `copy`.
- **TransNetV2 dep**: usare port **PyTorch** (evita TensorFlow hell). GPU 10–50× più veloce.
  Film 2h ≈ 172k frame: minuti su GPU, lento su CPU. Frame 48×27 via ffmpeg → RAM bassa.
- **AutoShot**: vantaggio headline su short-form; su feature film guadagno marginale vs TransNet
  → resta **opzionale**, non mandatory (evita over-engineering).

## Integrazione pesi neurali (step 3 / 7)
1. `pip install '.[neural]'`
2. vendorizzare l'architettura PyTorch in `scene_detector/models/{transnetv2,autoshot}.py`,
   esporre wrapper con `.predict(uint8[N,27,48,3]) -> float[N]`.
3. scaricare i pesi e passarli con `--transnet-weights` / `--autoshot-weights`.

## Deps
- base: `scenedetect[opencv]`, `numpy`, `typer` + **ffmpeg/ffprobe** (sistema).
- neural (extra opzionale): `torch`, `pillow`.

## Stato (2026-07-16)
- venv su python3.13 + base + neural installati e verificati: torch 2.13 (**MPS on**),
  scenedetect 0.7, opencv 5.0, numpy 2.5.1, typer 0.27.
- Unit test: **4/4**. Path **PySceneDetect end-to-end VERIFICATO** (clip sintetica 6s → 3 scene, durate esatte 2s).
- **Step 3 FATTO**: TransNetV2 vendorizzato (`models/transnetv2.py`) + pesi convertiti TF→PyTorch
  (`weights/transnetv2.pth`, 30MB) + wrapper windowing (`models/wrapper.py`) su **MPS**.
  End-to-end VERIFICATO sul sample (3 scene, come PySceneDetect). Conversione via venv
  usa-e-getta (TF 2.21 su py3.13; niente TF nel runtime).
- **Step 7 FATTO**: AutoShot vendorizzato (`models/autoshot/`, +einops) + pesi ufficiali
  (`ckpt_0_200_0.pth` da Baidu → `weights/autoshot.pth`) + wrapper (CPU) verificato end-to-end.
- **Step 8 FATTO**: ensemble TransNet+AutoShot verificato (0 disaccordi sul sample) + unit-test `reconcile`.
- **Step 10 FATTO**: `eval.py` (F1/P/R su boundary) + test. Suite: **12/12**.
- Prossimo: test su **film reale** (es. `Anna.mp4`). Tutte le fasi del piano completate.
