# Audit over-engineering — 07/23

Scansione dell'intero albero (`scene_detector/` 4738 righe su 54 file, `prove/`, `tests/`).
Ambito: **solo** complessità superflua. Bug di correttezza, sicurezza e performance sono fuori
scope — vanno a una review normale.

Il codice vendored (`detection/models/autoshot/supernet.py`, `detection/models/transnetv2.py`,
942 righe) è trattato a parte e in coda: modificarlo rischia il mismatch dello `state_dict` per
un guadagno piccolo.

Tag: `delete` (codice morto) · `stdlib` (roba che la standard library già fa) ·
`yagni` (astrazione con una sola implementazione, config che nessuno setta, layer con un
chiamante) · `shrink` (stessa logica, meno righe).

---

## Findings, taglio più grosso prima

### 1. `yagni` — il path `--low-mem` intero · ~120 righe

`FrameWindower` + `_pipe_frames` + `stream_small_windows` + `predict_stream` ×2 + il branch nei
due detector + il flag attraverso `cli` → `Config` → `pipeline`.

Costa ~120 righe per evitare 1,2 GB di picco su un film di 2h a 48×27 — e in ensemble
**raddoppia il decode** invece di dimezzare la RAM (niente decode-once). Resta solo
`read_small_frames`.

`detection/neural.py:46-126` · `detection/models/wrapper.py:51,121` · `detection/transnetv2.py:23`
· `detection/autoshot.py:23` · `cli.py:22` · `core/config.py:29`

### 2. `shrink` — `TransNetV2Detector` e `AutoShotDetector` sono la stessa classe · ~60 righe

Differiscono per `name`, testo dell'errore sui pesi, classe predictor, e il fatto che AutoShot
**butta le confidence che ha già** (non chiama `boundary_confidences`) — che non è una scelta di
design, è un ramo dimenticato. Una classe parametrica su `(name, predictor, hint)`, un file solo.

`detection/transnetv2.py` + `detection/autoshot.py` — 114 righe → ~50

### 3. `shrink` — `TransNetV2Predictor` e `AutoShotPredictor` · ~55 righe

Condividono padding, windowing, loop di inference, `sigmoid[25:75]`, `concat[:n]` — e li
condividono **due volte**, in `predict` e in `predict_stream`. Base con tre hook
(`_build`, `_to_tensor`, `_logits`).

`detection/models/wrapper.py` — 133 righe → ~75

### 4. `yagni` — `detection/base.py` + `detection/factory.py` · ~30 righe, 2 file

`SceneDetector` è `@runtime_checkable` ma non passa mai per un `isinstance`: serve solo come
annotazione di ritorno. E non descrive il contratto vero — il path ensemble chiama
`detect_from_frames`, `.input_size`, `.probs`, nessuno dei quali è dichiarato nel Protocol.

`factory.py` è una catena `if` da 7 righe più un `__all__` di 5 nomi che `detection/__init__.py`
riesporta diversi. La catena va in `detection/__init__.py`, i due file spariscono.

### 5. `delete` — `evaluate`, `f1_curve`, `read_scenes_txt` · ~35 righe

Zero chiamanti in produzione: il path benchmark della CLI (`benchmark.evaluate_video`) ricalcola
le stesse metriche inline. `read_scenes_txt` ha zero chiamanti **ovunque**. Le tiene vive solo
`tests/test_eval.py` — che è il sintomo classico del codice morto testato.

`evaluation/eval.py:43,119,138`

### 6. `shrink` — `cluster_faces` / `cluster_within_shot` · ~35 righe

La seconda è la prima più un set *must-not-link*. Una funzione con `frame_indices=None`.

Caveat: la prima è vettorizzata, la seconda cicla in Python. Unificare sul loop costa sullo
stadio 2 di `cluster_two_stage` (K medie di gruppo). K è piccolo, ma va misurato.

`recognition/identify.py:8,53`

### 7. `yagni` — la dep `scenedetect` · ~33 righe, 1 dep

`scenedetect>=0.7` (che tira dentro `opencv-python`) serve a un solo detector da 33 righe che
nient'altro tocca. Nessun `cv2` diretto nel codice.

Ed è in `dependencies` **base**, mentre il detector di default — TransNetV2 — sta dietro l'extra
`neural`: `pip install .` nudo installa opencv ma non il detector che usi davvero. Inversione da
sistemare comunque, anche tenendo la baseline.

`detection/pyscenedetect.py` · `pyproject.toml:11`

### 8. `shrink` — P/R/F1 scritto quattro volte · ~15 righe

Le stesse quattro righe in `prf1`, `transition_iou`, `benchmark.prf`, `runs_ab.summarize`.
Un `_prf(tp, fp, fn)` in `eval.py`, importato dagli altri tre.

`evaluation/eval.py:37,106` · `evaluation/benchmark.py:66` · `prove/runs_ab.py:166`

### 9. `shrink` — `pipeline.run` spacchetta `cfg` · 15 righe

20 campi di `cfg` copiati in locali con lo stesso identico nome, poi usati. Usa `cfg.x`.

`pipeline.py:23-37`

### 10. `yagni` — i wrapper `main_*` della CLI · 14 righe

`main()`, `main_index()`, `main_setup()`, `main_benchmark()`: pura delega. `typer.Typer` definisce
`__call__`, quindi gli entry point possono puntare direttamente agli oggetti app.

`cli.py:193-206` · `pyproject.toml:25-28`

### 11. `shrink` — `centroids_of` ≡ `average_embeddings` · ~10 righe

Stesso normalizza → media per gruppo → normalizza. `centroids_of` è
`dict(zip(ids, means))` sul risultato di `average_embeddings`.

`recognition/identify.py:94,148`

### 12. `delete` — `PySceneDetectDetector.adaptive` e `Config.pyscd_threshold` · ~8 righe

`adaptive` non è mai messo a `True`: la factory passa due posizionali e non esiste un flag CLI.
Via il parametro, il branch e l'import di `AdaptiveDetector`. `pyscd_threshold` è config che
nessuno setta.

`detection/pyscenedetect.py:9,23` · `core/config.py:30`

### 13. `delete` — `caption_manifest(save_every=…)` e `min_shot_frames` · ~10 righe

`save_every` vale sempre 1: il contatore `since` fa la guardia a una condizione sempre vera.
`min_shot_frames` lo passa non-zero soltanto un test.

`captioning/caption.py:128,167`

### 14. `delete` — le riesportazioni di `scene_detector/__init__.py` · 7 righe

`Scene`, `Config`, `build_detector`, `__version__`: nessuno le importa. È un'app, non una
libreria, e l'import eager tira dentro `detection` a ogni `import scene_detector`.

### 15. `stdlib` — escaping HTML a mano · 2 righe

`build_html` fa a mano la sostituzione di `&`/`<`/`>`. → `html.escape`.

`catalog/ui.py:215`

### 16. `delete` — `scene_detector/scopo.md`

Una riga di intento ("plug and play") che `install.sh` + `scene-detector-setup` già consegnano.
E sta dentro la cartella del package.

### 17. `delete` — vendored, bassa priorità · ~40 righe

`TransNetV2Supernet._init_weights`: 16 righe di init kaiming/uniform sovrascritte da
`load_state_dict` la riga dopo. Più `use_resnet_like_top` che solleva su entrambi i rami,
`chromosome` mai letto, e il set gemello di flag "not supported" in `models/transnetv2.py`.

Guadagno reale piccolo, rischio `state_dict` non nullo su codice di terze parti: da fare solo se
si sta già toccando il file.

`models/autoshot/supernet.py:73` · `models/transnetv2.py:17-23`

---

**net: -450 righe, -1 dep possibile.**

---

## Fuori scope, ma va detto

`tqdm` è importato in 6 moduli e non è dichiarato in `pyproject.toml`. L'installazione base si
rompe al primo decode. È un bug, non over-engineering — ma è a costo zero e viene sistemato
insieme al resto.

---

## Decisioni prese per questo branch

| # | Finding | Applicato | Nota |
|---|---------|-----------|------|
| 1 | `--low-mem` | ✅ | flag rimosso dalla CLI, dal `Config` e dal README |
| 2 | detector gemelli | ✅ | |
| 3 | predictor gemelli | ✅ | |
| 4 | `base.py` + `factory.py` | ✅ | |
| 5 | `evaluate` / `f1_curve` / `read_scenes_txt` | ✅ | via anche i test relativi |
| 6 | `cluster_faces` / `cluster_within_shot` | ✅ | |
| 7 | dep `scenedetect` | ❌ | PySceneDetect resta come baseline documentata |
| 8 | P/R/F1 ×4 | ✅ | |
| 9 | `pipeline.run` | ✅ | |
| 10 | wrapper `main_*` | ✅ | |
| 11 | `centroids_of` | ✅ | |
| 12 | `adaptive` / `pyscd_threshold` | ✅ | |
| 13 | `save_every` / `min_shot_frames` | ✅ | |
| 14 | riesportazioni `__init__` | ✅ | |
| 15 | `html.escape` | ✅ | |
| 16 | `scopo.md` | ✅ | |
| 17 | vendored | ❌ | rischio `state_dict` non giustificato dal guadagno |
| — | `tqdm` mancante | ✅ | aggiunto alle dipendenze base |
