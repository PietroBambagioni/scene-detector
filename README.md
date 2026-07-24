# Scene Detector

Prende un film e ne costruisce un **catalogo navigabile**: rileva i tagli fra inquadrature
(*shot boundary detection*), ritaglia ogni shot in una clip, e arricchisce ognuna con i
**personaggi riconosciuti**, i **dialoghi trascritti** e una **descrizione visiva**. Il risultato
è un `manifest.json` + una `index.html` da aprire nel browser.

Tutto gira **in locale**, su Apple Silicon: nessuna API esterna, nessun upload.

```bash
scene-detector "FILM.mp4" --all -o catalogo/
```

---

## Requisiti

- **Python ≥ 3.10** (testato su 3.13)
- **ffmpeg / ffprobe** nel PATH (`brew install ffmpeg`)
- Per il VLM: **Apple Silicon** (MLX). Il resto gira ovunque.

## Installazione

```bash
./install.sh            # venv + tutte le dipendenze + pesi neurali (88 MB)
./install.sh --models   # anche Whisper / VLM / volti (~4 GB), altrimenti scaricati al primo run
```

A mano, per un'installazione parziale:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .              # base: scenedetect, numpy, typer, tqdm
pip install -e '.[neural]'    # TransNetV2 / AutoShot: torch, pillow, einops
pip install -e '.[asr]'       # trascrizione: faster-whisper
pip install -e '.[vlm]'       # descrizione visiva: mlx-vlm (Apple Silicon)
pip install -e '.[faces]'     # personaggi: insightface, onnxruntime (CoreML)
pip install -e '.[all]'       # tutto ciò che serve a --all
scene-detector-setup          # pesi in weights/, sha256 verificato
```

Gli extra sono **davvero opzionali**: gli import dei modelli pesanti sono differiti dentro i
rami della pipeline, quindi `--asr` senza `--vlm` (o viceversa) funziona e un extra mancante non
rompe nulla finché non lo si chiede.

---

## Come funziona

`--all` esegue sei stadi in sequenza. Ognuno scrive nel manifest; gli stadi lunghi sono
**resumable**.

### 1 · Rilevamento shot

Il video viene decodificato **una sola volta** a 48×27 px via ffmpeg — la risoluzione d'ingresso
dei due modelli neurali — e i frame restano in RAM (~1,25 GB per un film di 2 h). Il detector
produce una **probabilità di boundary per frame**, non una lista di tagli:

```
probs  →  runs_to_ranges(th)  →  scenes_from_ranges  →  enforce_min_len(5)  →  list[Scene]
```

`runs_to_ranges` tratta una **corsa contigua** di frame sopra soglia come *una* transizione, non
come una fila di tagli: lo shot uscente la include e finisce dov'essa finisce, quello entrante
parte subito dopo. I range restano quindi **contigui e coprono tutti i frame**, e la larghezza
della giunta — che il vecchio `probs_to_ranges` buttava — finisce in `Scene.transition` e nel
manifest. `enforce_min_len` fonde nella precedente ogni scena più corta di `--min-scene-len`.
`Scene.end_frame` è **inclusivo**, qui e ovunque nel progetto.

> **La soglia di default è 0,05, non 0,5**, ed è accoppiata a `--min-scene-len 5`: cambiarne una
> sola peggiora il risultato. Misurato su 1634 transizioni reali annotate: il recall passa da
> 0,088 a 0,270 e sui soli stacchi netti da 0,81 a **0,93**, al prezzo di +32% di shot.
> Dettagli in [plan/TRANSIZIONI-GRADUALI.md](plan/TRANSIZIONI-GRADUALI.md).

In modalità `--ensemble` i due detector condividono la stessa decodifica e i loro boundary
vengono riconciliati (`detection/confidence.py`): i tagli entro `agreement_tol=5` frame si
fondono, gli altri entrano comunque ma finiscono in `flags` come «da rivedere». La
**confidenza** di ogni boundary è la probabilità per-frame di TransNetV2 al taglio — uno score
continuo, non un flag binario.

### 2 · Taglio delle clip

`segmentation/splitter.py` esporta ogni shot con ffmpeg, in parallelo su più core
(`-j`, default: tutti meno 2). Tre modalità, `--split-mode`:

| modalità | cosa fa | quando |
|---|---|---|
| `copy` (default) | stream copy: velocissimo, ma il taglio si allinea al keyframe più vicino (±GOP) | uso normale |
| `reencode` | H.264 CRF 18 + AAC, frame-accurate | quando la precisione al frame conta |
| `none` | **non taglia niente**: `clip: null` nel manifest e `video_src` col path relativo al film | collaudo, disco stretto |

Con `none` la UI riproduce ogni shot come intervallo sul file originale, usando i **media
fragments** (`#t=start,end`): stesso catalogo completo, zero duplicazione.

### 3 · Riconoscimento personaggi (`--faces`)

Campiona `--faces-frames` fotogrammi per shot, rileva i volti con **SCRFD** ed estrae gli
embedding **ArcFace** (512-d, L2-normalizzati) via InsightFace su CoreML. Poi li clusterizza in
personaggi ricorrenti **sull'intero film**, con un clustering greedy agglomerativo su distanza
coseno scritto in casa (nessuna dipendenza in più).

Il clustering è **a due stadi** e questo è il pezzo che conta:

1. **dentro ogni shot**, con vincolo *must-not-link* per frame — due volti visti nello **stesso
   fotogramma** sono due persone diverse per quanto si somiglino. È ciò che impedisce a un
   campo/controcampo di collassare in un'unica identità.
2. **fra gli shot**, sui gruppi mediati dello stadio 1: la media di più viste cancella il rumore
   di posa e fuoco che fa deragliare il singolo frame.

Misurato su un film di 3h33: **−31% di cluster a parità di copertura degli shot** rispetto al
clustering per singolo volto. Un pre-filtro `--faces-min-px` scarta i volti troppo piccoli,
il cui embedding è rumore.

Con `--faces-gallery <dir>` (una sottocartella `<Nome>/` con foto per personaggio) i cluster
prendono i nomi veri; senza gallery restano `Personaggio N`, **rinominabili nella UI**.

### 4 · Trascrizione dialoghi (`--asr`)

**faster-whisper** (Whisper via CTranslate2). L'audio non viene passato in un blocco unico: un
**VAD** individua il parlato e la trascrizione avviene su **finestre brevi e indipendenti** da
30 s. Serve a due cose — impedisce per costruzione i loop del decoder (ogni finestra riparte da
zero) e recupera parlato che altrimenti si perde: +18% di tempo per +7% di parole, misurato.

Due difese specifiche, entrambe nate da bug reali:

- **Rilevamento lingua sul parlato, non sull'audio grezzo.** `speech_head` concatena i primi 30 s
  di *parlato* estratti dalle finestre VAD e rileva la lingua su quelli. Sul grezzo, un film che
  si apre con un cartello muto veniva classificato `en` con confidenza 0,62 e trascritto tutto in
  inglese.
- **Filtro allucinazioni.** Su audio degradato Whisper fabbrica frasi-tipo («Grazie a tutti»),
  finti crediti di sottotitolaggio e loop di ripetizione. `is_hallucination` li scarta a monte
  cercando il periodo minimo della sequenza di parole.

I segmenti risultanti vengono assegnati agli shot per **punto medio** (`transcription/align.py`),
con una scansione lineare: ogni segmento finisce in esattamente uno shot, nessuna duplicazione.

### 5 · Descrizione visiva (`--vlm`)

Campiona `--vlm-frames` fotogrammi per shot (leggermente rientrati dai bordi, per non prendere i
frame di taglio) e li passa a **Qwen3-VL-8B-Instruct-4bit** via **mlx-vlm**. Il prompt chiede una
descrizione concreta di 1-2 frasi in italiano; i personaggi riconosciuti allo stadio 3 e il
dialogo dello stadio 4 entrano come **contesto** — marcati esplicitamente come tali, con
l'istruzione di non parafrasarli, o il modello si mette a raccontare la trama invece di
descrivere l'inquadratura.

`temperature=0`: per un catalogo la riproducibilità vale più della varietà.

È lo stadio più lento (~5 s/shot) ed è **resumable**: il manifest viene scritto su disco *prima*,
e un run interrotto riparte saltando gli shot già descritti.

### 6 · Manifest, UI, galleria

`manifest.json` è il backbone: lo costruisce lo stadio 1 con `description`/`dialogue`/`characters`
come placeholder, e ogni stadio successivo lo riempie e lo riscrive. È anche il meccanismo di
resume — non c'è nessuno stato altrove.

```jsonc
{
  "video": "FILM.mp4", "fps": 23.976, "n_frames": 192701, "duration": 8037.5,
  "detector": "transnet", "n_shots": 2426,
  // ordinato per n_shots decrescente
  "cast": [ { "id": 0, "name": "Personaggio 1", "n_faces": 262, "n_shots": 76, "shots": [...] } ],
  "shots": [
    { "index": 0, "start_frame": 0, "end_frame": 148,
      "start_time": 0.0, "end_time": 6.214,
      "clip": "scene-001.mp4",        // null con --split-mode none
      "confidence": 0.98,
      // presente solo se lo shot si apre con una transizione graduale
      "transition": { "start_frame": 8464, "end_frame": 8467, "n_frames": 4 },
      "description": "…", "dialogue": "…", "characters": [0, 3] }
  ]
}
```

`index.html` è una pagina autonoma (nessun asset esterno): player, timeline cliccabile, lista
degli shot, **ricerca full-text nei dialoghi**, card del cast con rinomina, ed export delle
modifiche. Una seconda pagina, la **galleria**, viene rigenerata a ogni run in cima alla
cartella di output e raccoglie tutti i film catalogati.

Ogni run scrive anche la telemetria in `logs/run-<ts>/`: configurazione completa, ambiente, e
durata/esito di ogni stadio.

---

## Componenti

### Shot boundary detection

| Modello | `-d` | Tipo | Device | Pesi | Ruolo |
|---|---|---|---|---|---|
| **TransNetV2** | `transnet` | CNN 3D (DDCNN) | MPS | 31 MB | primario, default |
| **AutoShot** | `autoshot` | NAS su spazio derivato da TransNetV2 | CPU | 57 MB | seconda opinione |
| **PySceneDetect** | `pyscenedetect` | classico, content-based | CPU | nessuno | baseline, zero setup |
| **Ensemble** | `--ensemble` | TransNet + AutoShot | MPS+CPU | entrambi | riconciliazione + flag sui disaccordi |

**AutoShot gira su CPU e non su MPS**: la sua `ColorHistograms` usa operazioni intere
(bit-shift, segment-sum) che MPS non supporta.

### Arricchimento

| Cosa | Stack | Note |
|---|---|---|
| **Volti** | InsightFace `buffalo_l` — SCRFD (detection) + ArcFace (embedding) | ONNX Runtime su **CoreML**, fallback CPU |
| **Clustering** | greedy agglomerativo coseno, due stadi, must-not-link | scritto in casa, solo NumPy |
| **ASR** | faster-whisper (Whisper su CTranslate2), `large-v3-turbo` | CPU multi-thread, VAD + finestre da 30 s |
| **VLM** | mlx-vlm + Qwen3-VL-8B-Instruct-4bit | MLX, Apple Silicon, greedy |

### Base

**Typer** (CLI) · **PyTorch** + **einops** (inference neurale) · **NumPy** · **OpenCV** via
`scenedetect` · **ffmpeg/ffprobe** (probe, decode, taglio) · **tqdm** · **psutil** (telemetria)
· **pytest**.

---

## Comandi

Quattro entry point.

### `scene-detector` — la pipeline

```bash
scene-detector FILM.mp4 -d pyscenedetect -o clips/          # baseline classica, nessun peso
scene-detector FILM.mp4 -o clips/                           # neurale (default), pesi auto da weights/
scene-detector FILM.mp4 --ensemble -o clips/                # TransNet + AutoShot
scene-detector FILM.mp4 --all --asr-lang it -o catalogo/    # tutto, lingua forzata
scene-detector FILM.mp4 --all --split-mode none -o catalogo/ # catalogo senza duplicare il film
```

| Flag | Default | Descrizione |
|---|---|---|
| `VIDEO` | — | film in ingresso (posizionale) |
| `-o, --output-dir` | `clips` | cartella radice; l'output va in `<dir>/<nome-film>/` |
| `--all` | off | pipeline completa: detection + split + faces + ASR + VLM |
| `--max` | off | `--all` + `reencode` frame-accurate + multi-core |
| `-d, --detector` | `transnet` | `transnet` \| `autoshot` \| `pyscenedetect` |
| `--ensemble` | off | TransNet + AutoShot con riconciliazione e flag sui disaccordi |
| `--threshold` | `0.05` | soglia di boundary sulle probabilità neurali |
| `--min-scene-len` | `5` | frame minimi per shot (sotto, viene fuso nel precedente) |
| `--split-mode` | `copy` | `copy` \| `reencode` \| `none` |
| `-j, --jobs` | `0` | processi ffmpeg paralleli per il taglio (0 = core − 2) |
| `--transnet-weights` | auto da `weights/` | pesi TransNetV2 |
| `--autoshot-weights` | auto da `weights/` | pesi AutoShot |
| `--asr` | off | trascrivi i dialoghi |
| `--asr-model` | `large-v3-turbo` | `tiny/base/small/medium/large-v3/large-v3-turbo` o path |
| `--asr-lang` | auto | lingua ISO (es. `it`); auto = rilevata sul parlato |
| `--asr-threads` | `0` | thread CPU per l'ASR (0 = core − 2) |
| `--vlm` | off | descrizione visiva per shot |
| `--vlm-model` | `mlx-community/Qwen3-VL-8B-Instruct-4bit` | repo `mlx-community` o path locale |
| `--vlm-frames` | `3` | frame campionati per shot |
| `--faces` | off | riconoscimento personaggi |
| `--faces-gallery` | — | cartella `<Nome>/*.jpg` per etichettare i personaggi |
| `--faces-frames` | `6` | frame campionati per shot |
| `--faces-threshold` | `0.5` | soglia coseno per clustering / match gallery |
| `--faces-min-score` | `0.5` | soglia `det_score`: scarta i volti deboli |
| `--faces-min-px` | `50` | lato minimo del volto in px: sotto, l'embedding è rumore |

### `scene-detector-setup` — pesi e modelli

```bash
scene-detector-setup                 # TransNetV2 + AutoShot (88 MB), sha256 verificato
scene-detector-setup --models        # anticipa anche Whisper / VLM / volti (~4 GB)
scene-detector-setup --force         # riscarica anche ciò che c'è già
```

Verifica anche che `ffmpeg`/`ffprobe` siano nel PATH.

### `scene-detector-benchmark` — valutazione su ground truth pubblico

```bash
scene-detector-benchmark --limit 50            # 50 video del test set di SHOT
scene-detector-benchmark --limit 0 --ensemble  # tutti i 200, in ensemble
```

| Flag | Default | Descrizione |
|---|---|---|
| `--data-dir` | `prove/shot-dataset` | dove tenere ground truth e video |
| `--limit` | `50` | quanti video di test usare (0 = tutti i 200) |
| `--ensemble` | off | valuta l'ensemble invece del solo TransNet |
| `--tol` | `5` | tolleranza in frame per il match sui boundary |
| `--min-iou` | `0.5` | IoU minimo perché una transizione conti come TP |

Scarica il test set di **SHOT** (AutoShot, CVPR-W 2023: 200 video, 2716 shot, 2516 boundary di
cui 438 transizioni graduali **col loro range**) dallo stesso mirror HuggingFace dei pesi.
Niente Baidu, niente auth, **niente annotazione a mano**. Degli ~20 GB di archivi legge l'indice
degli zip remoti via range HTTP e scarica solo i video che servono.

### `scene-detector-index` — galleria

```bash
scene-detector-index -o clips/       # rigenera <out>/index.html scandendo i cataloghi presenti
```

---

## Pesi

Non stanno nel repo (`weights/` è in `.gitignore`): li scarica `scene-detector-setup`, che
verifica lo **sha256** di ogni file e scrive su un temporaneo, rinominando solo dopo la verifica
— un download interrotto non lascia un peso corrotto al suo posto. Il registro sta in
[`core/weights.py`](scene_detector/core/weights.py).

Nessuno dei due upstream pubblica un artefatto scaricabile — TransNetV2 va convertito da
TensorFlow, AutoShot sta su Baidu con passcode — ma entrambi hanno un **mirror pubblico su
HuggingFace**: AutoShot identico byte per byte, TransNetV2 una conversione diversa (altra
serializzazione torch) ma con **90/90 tensori uguali**, verificato con `torch.equal`. Download
completo in ~9 s.

Un file già presente in `weights/` **non viene sovrascritto**, anche se il suo hash differisce da
quello del mirror: chi ha convertito i pesi a mano ha un file valido con un hash diverso.

### Conversione a mano di TransNetV2 (non serve più, ma resta valida)

TensorFlow serve **solo** alla conversione, una-tantum; il runtime usa solo torch.

```bash
git clone --depth 1 https://github.com/soCzech/TransNetV2.git
python3.13 -m venv .venv_convert && .venv_convert/bin/pip install tensorflow torch numpy
cd TransNetV2/inference-pytorch
../../.venv_convert/bin/python convert_weights.py --tf_weights ../inference/transnetv2-weights/ --test
# -> transnetv2-pytorch-weights.pth   (copia in ../../weights/transnetv2.pth)
```

---

## Valutazione

`scene_detector.evaluation.eval` offre **due famiglie di metriche**, e servono a cose diverse.

```python
from scene_detector.evaluation.eval import (
    boundaries_from_scenes, boundaries_from_ranges, prf1,
    transitions_from_ranges, transition_iou,
)

# ground truth = [(start, end), …] shot inclusivi
b = prf1(boundaries_from_scenes(pred), boundaries_from_ranges(gt), tol=5)
# {precision, recall, f1, tp, fp, fn}

t = transition_iou(transitions_from_ranges([(s.start_frame, s.end_frame) for s in pred]),
                   transitions_from_ranges(gt), min_iou=0.5)
# {precision, recall, f1, tp, fp, fn, mean_iou, min_iou, matched}
```

**L'F1 sui boundary da solo inganna.** Confronta punti con punti, quindi è cieco alla *larghezza*
delle transizioni: si può avere F1 1,00 e transition IoU 0,08 sullo stesso dato. Esempio reale —
dissolvenza di 24 frame nel ground truth, il detector piazza un taglio secco nel mezzo:

| | |
|---|---|
| F1 boundary (`tol=15`) | **1,00** — «perfetto» |
| `transition.mean_iou` | **0,083** — la dissolvenza non è delimitata |

Quindi: **cita sempre `tol` insieme all'F1**, e usa `transition_iou` se il materiale ha
dissolvenze o fade. Su un film a soli hard cut la metrica range-based dice poco per costruzione
(tutte le transizioni sono da 2 frame): è sul materiale con transizioni graduali che separa i
detector.

**Su un ground truth misto, leggi la metrica per tipo.** 55 transizioni graduali annegate in
~2500 hard cut fanno sembrare il meanIoU 0,94 quando sulle graduali è 0,21.

`transitions_from_ranges` ricava le transizioni dagli shot: contigui = hard cut (i 2 frame a
cavallo dello stacco), buco fra due shot = transizione graduale larga quanto il buco.

Per la valutazione end-to-end su più video c'è `evaluation/benchmark.py`, che aggrega in
**micro** (tp/fp/fn sommati su tutti i video prima di calcolare P/R/F1: un video con 58 shot
deve pesare più di uno con 1).

---

## Test

```bash
.venv/bin/python -m pytest tests/ -q                    # 79 test, ~0,2 s
.venv/bin/python -m pytest tests/test_eval.py -q        # un singolo file
.venv/bin/python -m pytest tests/ -q -k transition      # un singolo caso
```

I test non toccano video né pesi: girano in due decimi di secondo e coprono la logica pura
(post-processing, riconciliazione, clustering, allineamento dialoghi, manifest, metriche).

---

## Struttura

Un package per stadio della pipeline:

```
scene_detector/
  cli.py                    # entrypoint Typer (flag -> Config)
  pipeline.py               # orchestrazione degli stadi
  core/
    config.py               # Config + enum DetectorKind / SplitMode
    scene.py                # datamodel Scene + scenes_from_ranges + enforce_min_len
    weights.py              # registro pesi (url + sha256) e download verificato
    cpu.py                  # resolve_workers
    telemetry.py            # logs/run-<ts>/
  io/video.py               # probe ffprobe -> VideoInfo
  detection/
    neural.py               # decode + probs_to_ranges + i due detector
    pyscenedetect.py
    confidence.py           # riconciliazione ensemble
    models/                 # architetture vendored (TransNetV2, AutoShot) + wrapper
  segmentation/splitter.py  # export clip via ffmpeg, parallelo
  transcription/
    asr.py                  # faster-whisper + VAD + filtro allucinazioni
    align.py                # assegna i segmenti agli shot
  captioning/caption.py     # sampling frame + backend MLX + resume
  recognition/
    faces.py                # InsightFace + orchestrazione + gallery
    identify.py             # clustering a due stadi + match gallery (logica pura)
  catalog/
    manifest.py             # manifest.json
    ui.py                   # UI per-film
    gallery.py              # galleria multi-film
  evaluation/
    eval.py                 # metriche: boundary (prf1) e transizioni (transition_iou)
    benchmark.py            # valutazione multi-video, aggregazione micro
    shot_dataset.py         # download del test set di SHOT (zip remoti via range HTTP)
```

---

## Note & gotcha

- **Memoria**: i frame 48×27 stanno interi in RAM, ~1,25 GB per un film di 2 h a 24 fps. È una
  scelta: il path a streaming costava 120 righe e in ensemble raddoppiava la decodifica.
- **Taglio**: `copy` è veloce ma si allinea ai keyframe, quindi su uno shot corto l'errore pesa
  in proporzione. Se conta, `reencode`.
- **Film lunghi**: `--split-mode copy` (default), altrimenti migliaia di clip in `reencode` sono
  ore. Le clip occupano circa quanto il film: se non servono, `--split-mode none`.
- **Output per film**: più film sulla stessa `-o` non si mescolano (ognuno in `<nome-film>/`).
- **`tqdm` in un file di log** scrive una riga per aggiornamento e seppellisce l'output utile:
  passa `progress=False` quando non sei su un terminale.
- **Un pickle da un mirror di terze parti è codice eseguibile**: il ground truth di SHOT viene
  caricato con un unpickler ristretto (`_SafeUnpickler`), che accetta solo la ricostruzione di
  array NumPy e alza su qualunque altro simbolo.

---

## Crediti e licenze

| Componente | Autori | Licenza |
|---|---|---|
| [TransNetV2](https://github.com/soCzech/TransNetV2) | Souček & Lokoč | MIT |
| [AutoShot](https://github.com/wentaozhu/AutoShot) | Zhu et al., CVPR-W 2023 | MIT |
| [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) | Castellano | BSD-3 |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | SYSTRAN | MIT |
| [mlx-vlm](https://github.com/Blaizzy/mlx-vlm) · [Qwen3-VL](https://github.com/QwenLM/Qwen3-VL) | Blaizzy · Alibaba | MIT · Apache-2.0 |
| [InsightFace](https://github.com/deepinsight/insightface) | Deng et al. | codice **MIT** |

⚠️ Il model package **`buffalo_l`** di InsightFace ha una **licenza separata: solo ricerca non
commerciale**. È distinta dalla licenza MIT del codice.

Le architetture di TransNetV2 e AutoShot sono vendorate in `detection/models/` (entrambe MIT).
Regola adottata per il resto: **codice senza licenza si scarica al setup, non si vendora** —
stesso schema di `core/weights.py` per i pesi.
