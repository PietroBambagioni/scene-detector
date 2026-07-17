# Plan — Fix & Miglioramenti

Elenco dei miglioramenti individuati durante la review del progetto. Ordinati per
rapporto valore/rischio. Ogni voce ha: file coinvolti, cosa cambia, tradeoff, stato.

Legenda stato: `[ ]` da fare · `[x]` fatto · `🔴` alto valore · `🟡` medio · `⚪️` minore.

---

## Fatti

### [x] 🟡 Deprecation PyTorch in `gather_nd` (AutoShot)
- **File**: `scene_detector/models/autoshot/supernet.py:188`
- **Problema**: `params[indices]` con `indices` = lista Python (sequenza non-tuple) →
  `UserWarning` e, da **PyTorch 2.9**, semantica diversa (`params[torch.tensor(indices)]`)
  che darebbe risultati sbagliati o un errore.
- **Fix**: `params[tuple(indices)]` — è esattamente la semantica applicata oggi da PyTorch
  alla sequenza non-tuple, quindi **output invariato** e future-proof per ≥ 2.9.
- **Nota**: file vendorizzato (upstream `wentaozhu/AutoShot`). Se si riallinea il vendor,
  riportare questa patch.

---

## Da fare

### [x] 🔴 L'ensemble decodifica il film due volte
- **File**: `scene_detector/cli.py:96-104`, `detectors/transnetv2_detector.py`,
  `detectors/autoshot_detector.py`, `detectors/_neural.py`
- **Problema**: in `--ensemble` entrambi i detector chiamano `read_small_frames(path, 48, 27)`
  in modo indipendente. L'input ai due modelli è **identico** (stesso `input_size = (27,48)`),
  ma la decodifica ffmpeg dell'intero film — il pezzo I/O-bound più lento della detection —
  viene pagata due volte.
- **Fix (fatto)**: separato *read frames* da *predict*. I detector neurali espongono ora
  `detect_from_frames(frames, video)`; in ensemble `cli.py` decodifica **una volta**
  (`read_small_frames(..., desc="[decode] frames")`, con assert `input_size` uguale) e passa
  lo stesso array a entrambi i predictor. Dimezza il tempo di detection in ensemble.
- **Direzione scelta**: decode-once (non streaming). Confligge con lo streaming del punto
  "Tutto il film in RAM" — quest'ultimo resta da fare solo se la RAM diventa un vincolo reale.

### [ ] 🟡 `min_scene_len` applicato due volte
- **File**: `detectors/_neural.py:49` (`probs_to_ranges`) + `cli.py:72` (`enforce_min_len`)
- **Problema**: due semantiche diverse sullo stesso vincolo. `probs_to_ranges` **sopprime**
  il boundary (sposta il taglio in avanti); `enforce_min_len` **fonde** nella scena precedente.
  Su shot corti danno risultati diversi.
- **Fix**: togliere il vincolo da `probs_to_ranges` (che deve solo tradurre prob→range) e
  lasciare `enforce_min_len` come unica autorità.
- **Tradeoff**: nessuno rilevante; serve un test che fissi il comportamento atteso.

### [ ] 🟡 Tutto il film caricato in RAM
- **File**: `detectors/_neural.py:7` (`read_small_frames`)
- **Problema**: materializza `[N,27,48,3]` interi (~1.2 GB a 2h, >2 GB per il film da 3.5h).
- **Fix**: streaming windowed inference — leggere dalla pipe ffmpeg una finestra (100 frame,
  passo 50) alla volta e predire, senza tenere tutti i frame. RAM da GB a MB.
- **Tradeoff**: complica il codice (buffer scorrevole) e rompe il riuso «decode-once» del
  fix ensemble. Da fare solo se la RAM è un vincolo reale sul target.

### [ ] 🟡 Fragilità API di `mlx-vlm`
- **File**: `scene_detector/caption.py:90-93`, `pyproject.toml:19`
- **Problema**: `generate()` riceve `temperature=`/`max_tokens=`; nelle versioni recenti di
  mlx-vlm la firma è cambiata (sampler). `pyproject` pinna solo `mlx-vlm>=0.1` → un upgrade
  può rompere il caption.
- **Fix**: pinnare un range testato (es. `>=0.1,<0.7`) **oppure** incapsulare la chiamata in
  un adapter tollerante alla firma.
- **Tradeoff**: il pin è più semplice ma va aggiornato a mano; l'adapter è più robusto ma
  aggiunge codice.

### [ ] 🟡 Resilienza per-shot mancante (VLM/ASR)
- **File**: `scene_detector/caption.py:133-145`
- **Problema**: se `captioner.describe` lancia su **un** shot, muore l'intero step; un shot
  "velenoso" blocca ogni riavvio nonostante il resume.
- **Fix**: `try/except` per-shot che logga e lascia `description=None` (già gestito dalla UI
  editabile). Il batch prosegue.
- **Tradeoff**: nasconde errori sistematici → loggare il conteggio dei fallimenti a fine run.

## Minori / cleanup

### [ ] ⚪️ Nessun controllo di versione
- Il progetto non è un repo git. `git init` + primo commit (`.gitignore` già presente).

### [ ] ⚪️ `torch.load` incoerente
- **File**: `models/wrapper.py:24` (TransNet, senza flag) vs `:69` (AutoShot, `weights_only=True`).
  Allineare TransNet a `weights_only=True`.

### [ ] ⚪️ Coverage sulla logica di boundary
- `probs_to_ranges`, `enforce_min_len`, `probe` sono funzioni pure non testate — proprio dove
  i bug si nascondono. Aggiungere unit-test.

### [ ] ⚪️ `Config` bypassato
- **File**: `cli.py` — i parametri ASR/VLM/`jobs` viaggiano come argomenti sciolti invece che
  nel dataclass `Config`. Incoerenza architetturale (non un bug).

### [ ] ⚪️ `assign_dialogue` O(shot × segmenti)
- **File**: `align.py:14-19` — con shot ordinati diventa lineare con un puntatore. Trascurabile
  finché non si sale di scala.

### [ ] ⚪️ File spuri
- `text.txt` (vuoto) e `.DS_Store` da rimuovere / ignorare.

---

## Piano 1 — Logging & telemetria di esecuzione 🟡 ✅ FATTO

> **Stato**: implementato in `scene_detector/telemetry.py` (il modulo vivrà in `core/` dopo il
> Piano 2). `Telemetry.step()` context manager + `ResourceSampler` (thread psutil, CPU%/RSS
> medio+picco) + `RunStats` incrementale. Output in `<out>/<film>/logs/run-<ts>/`
> (`run.log` + `config.json` + `run_stats.json`) con symlink `latest`. Gli `echo` di `cli.py`
> migrati a `logging`. Dipendenza aggiunta: extra `obs = ["psutil>=5.9"]` (Opzione A).
> Verificato con smoke `--ensemble` e detector singolo su clip reale.

### Obiettivo
Rendere osservabile un run: **tempo per step**, **uso CPU**, **memoria (RSS di picco)**,
**disco** (spazio output + spazio libero), throughput. Oggi c'è solo `typer.echo` + barre tqdm:
nessun dato strutturato, nessuna metrica risorse. Serve per capire dove va il tempo su film
interi (~1.5–2h di run) e per dimensionare RAM/disco prima di lanciare.

### Cosa loggare — risorse (per step: detection · split · ASR · VLM · manifest/UI)
- **Tempo**: start/end/elapsed di ogni step + totale wall-clock.
- **CPU**: `%` medio e di picco durante lo step (campionamento).
- **Memoria**: RSS di picco del processo (+ figli ffmpeg/torch dove rilevante).
- **Disco**: dimensione cumulata di `<out>/<film>/` a fine step + spazio libero sul volume.

### Cosa loggare — config & contesto del run (all'avvio, una volta)
Snapshot completo di *come* è stato lanciato il run, per riproducibilità e debug:
- **Comando**: `argv` completo + timestamp di inizio (ISO) + host + cwd.
- **Flag/opzioni risolti** (dopo l'espansione di `--all`/`--max`): `detector`, `ensemble`,
  `split_mode`, `threshold`, `min_scene_len`, `asr`/`asr_model`/`asr_lang`/`asr_threads`,
  `vlm`/`vlm_model`/`vlm_frames`, `jobs`, `output_dir`, path dei pesi (transnet/autoshot).
- **Mode effettivi**: detector attivo (o `ensemble`), `split-mode` (copy/reencode),
  device di inference (`mps`/`cpu`), `workers` risolti (split e ASR, dopo `resolve_workers`).
- **Video**: nome, `fps`, `n_frames`, `duration`, `width×height`.
- **Ambiente**: versioni di python, torch (+ `mps.is_available`), ffmpeg, numpy, scenedetect,
  faster-whisper, mlx-vlm (quelle installate/rilevanti al run).

### Cosa loggare — esiti per step (a fine step)
- **detection**: `n_shots`, threshold usata; in ensemble anche `n_flag` + lista frame in disaccordo.
- **split**: n clip scritte, `split_mode`, `workers`, byte totali.
- **ASR**: lingua rilevata, n segmenti, n shot con dialogo, modello + threads.
- **VLM**: shot descritti / saltati (micro-shot) / già fatti (resume), modello + `vlm_frames`.
- **manifest/UI**: path di `manifest.json` e `index.html`.

### Design
Nuovo modulo `core/telemetry.py` (dopo il Piano 2; oggi `scene_detector/telemetry.py`):
- `step(name)` — context manager: logga inizio/fine, misura `time.perf_counter`, avvia/ferma
  un campionatore risorse, accumula in un record.
- `ResourceSampler` — thread in background che campiona ogni ~0.5s CPU% e RSS
  (`psutil.Process`), tiene media/picco. Si ferma alla chiusura dello step.
- `RunStats` — raccoglie i record e li serializza.

Integrazione in `cli.py`/`pipeline.py`: avvolgere ogni fase in `with step("detection"): …`.
Le barre tqdm restano (throughput live); la telemetria aggiunge il consuntivo.

### Output — cartella di log dedicata
Tutti i log in una **cartella** `<out>/<film>/logs/`, un sotto-folder per run (timestampato)
così i run successivi non si sovrascrivono:
```
<out>/<film>/logs/
  run-2026-07-17_02-31-05/
    run.log          # log umano leggibile (via logging, non più echo sparsi)
    config.json      # snapshot config & contesto (comando, flag risolti, mode, video, ambiente)
    run_stats.json   # metriche per step (tempo, CPU%, RSS, disco) + esiti + totali
  latest -> run-2026-07-17_02-31-05/   # symlink all'ultimo run (comodità)
```
- Il nome del sotto-folder = `run-<timestamp>` all'avvio; la cartella è creata prima del primo step.
- `config.json` scritto **all'inizio** (così un crash precoce lascia comunque la config).
- `run_stats.json` aggiornato **a fine di ogni step** (append incrementale): un run interrotto
  conserva le metriche degli step già conclusi.
- Il manifest resta il catalogo shot: le metriche **non** vanno in `manifest.json`.

### Scelta dipendenza (da confermare)
- **Opzione A — `psutil`** (consigliata): campionamento live CPU%/RSS, cross-platform, disco
  via `psutil`/`shutil.disk_usage`. Costo: +1 dipendenza (extra `obs`), leggera e diffusa.
- **Opzione B — solo stdlib**: `resource.getrusage(RUSAGE_SELF).ru_maxrss` (picco RSS, no CPU%
  live), `time`, `shutil.disk_usage`. Zero dipendenze ma niente CPU% né sampling nel tempo →
  copre solo parte di ciò che è stato chiesto.
→ La richiesta ("uso cpu, memoria") implica sampling → **A**. Aggiungere extra
  `obs = ["psutil>=5.9"]` in `pyproject`.

### Step (con verifica)
1. `telemetry.step` + `RunStats` (solo tempo) → verify: elapsed per step stampato e in JSON.
2. `ResourceSampler` (CPU%/RSS picco) → verify: valori plausibili su uno step lungo (inference).
3. Disco (size output + free) per step → verify: numeri coerenti con `du`/`df`.
4. Migrare gli `echo` a `logging` + `run.log` → verify: log su file e console, livelli sensati.
5. Scrivere `run_stats.json` → verify: schema stabile, un run reale (clip 2 min) lo produce.

### Tradeoff
- Il sampler è un thread: overhead trascurabile, ma va chiuso in modo pulito (finally) per non
  lasciare thread appesi se uno step lancia.
- Non trasformare il progetto in un framework di observability: niente Prometheus/OpenTelemetry
  — sono file locali, in linea con lo scope (uso personale/batch).

---

## Piano 2 — Ristrutturazione in package per dominio 🟡

### Obiettivo
Passare dal layout piatto attuale (11 moduli nella root del package) a package per **stadio
della pipeline**, così che la struttura racconti il flusso e la crescita (telemetria, nuovi
detector, nuovi backend) non ingrossi la root.

### Motivazione / tradeoff (onesto)
Il progetto è ~2.900 righe: il layout piatto **oggi funziona** e non è un problema. Questa
ristrutturazione è un investimento per leggibilità/onboarding e per accogliere i piani sopra
(es. `core/telemetry.py`), **non** un fix di un difetto. Costo reale: **churn degli import**
(quasi ogni file cambia import relativi) + aggiornare `entry_points`/`packages.find`. Va fatta
in un unico commit atomico con i test a fare da rete. → **git init prima** (vedi cleanup).

### Target tree
```
scene_detector/
  __init__.py
  cli.py                 # thin: parse flag → chiama pipeline
  pipeline.py            # orchestrazione degli step (estratta da cli.py)
  core/
    config.py            # Config, DetectorKind, SplitMode
    scene.py             # Scene + enforce_min_len
    cpu.py               # resolve_workers
    telemetry.py         # (Piano 1)
  io/
    video.py             # probe → VideoInfo   (già cartella)
  detection/
    base.py              # Protocol SceneDetector
    factory.py           # build_detector (era detectors/__init__.py)
    neural.py            # read_small_frames + probs_to_ranges (era _neural.py)
    pyscenedetect.py
    transnetv2.py
    autoshot.py
    confidence.py        # reconcile (logica d'ensemble → sta con la detection)
    models/              # architetture + wrapper (vendor)
      transnetv2.py
      wrapper.py
      autoshot/
  segmentation/
    splitter.py
  transcription/
    asr.py
    align.py
  captioning/
    caption.py
  catalog/
    manifest.py
    ui.py
  evaluation/
    eval.py
```
(ogni cartella con `__init__.py`.)

### Mappa spostamenti
| Da | A |
|---|---|
| `config.py`, `scene.py`, `cpu.py` | `core/` |
| `detectors/*` | `detection/` (`_neural.py`→`neural.py`, `__init__.py`→`factory.py`) |
| `confidence.py` | `detection/confidence.py` |
| `models/*` | `detection/models/` |
| `splitter.py` | `segmentation/` |
| `asr.py`, `align.py` | `transcription/` |
| `caption.py` | `captioning/` |
| `manifest.py`, `ui.py` | `catalog/` |
| `eval.py` | `evaluation/` |
| logica di orchestrazione in `cli.py` | nuovo `pipeline.py` |

### Step (con verifica)
1. **git init + commit** dello stato attuale → rete di sicurezza per lo spostamento.
2. Creare le cartelle + `__init__.py`; spostare i file (un dominio alla volta).
3. Aggiornare import relativi + `pyproject` (`packages.find`, `entry_points` resta
   `scene_detector.cli:main`) + i path negli import dei test.
4. Estrarre l'orchestrazione da `cli.py` a `pipeline.py` (cli diventa solo parsing).
   → verify: `pytest tests/` **15/15 verde**.
5. Smoke end-to-end sulla clip 2 min (`--all`) → verify: manifest + UI + clip identici a prima.

### Note
- Mantenere i nomi vendor invariati sotto `detection/models/autoshot/` (facilita il riallineo
  upstream + la patch `gather_nd`).
- Import pubblici in `scene_detector/__init__.py`: esporre `Scene`, `Config`, `build_detector`
  per non rompere eventuali usi esterni (es. `eval` in README).
- Non spingersi oltre: niente `src/` layout o namespace package se non serve — sarebbe
  over-engineering per la dimensione attuale.

---

## Piano 3 — Launcher UI: galleria multi-film 🟡

### Obiettivo
Oggi la UI è un `index.html` **per film** in `<out>/<film>/`: per vederne uno lo si apre a mano,
e con più film non c'è una pagina da cui **scegliere**. Serve un punto d'ingresso unico che
elenchi i cataloghi presenti e apra quello scelto.

### Design (Opzione A — consigliata: galleria statica, zero deps)
- Sotto-comando `scene-detector index -o <out>` (o generazione automatica a fine run): scandisce
  `<out>/*/manifest.json`, scrive `<out>/index.html`.
- La galleria è HTML self-contained (stessa filosofia della UI attuale): una card per film con
  titolo, n_shot, durata, detector, e link a `<film>/index.html`. Opz. una thumbnail
  (primo frame del primo shot, già estraibile con la logica di `caption.py`).
- Si apre con doppio click (`file://`): le clip sono file locali per-shot → seek ok, niente server.

### Design (Opzione B — fallback: mini-server)
- `scene-detector serve -o <out>`: `http.server` radicato in `<out>` + apertura browser sulla
  galleria. Da tenere in tasca **solo** se un browser blocca i media via `file://` (non atteso
  qui, ma su alcune configurazioni sì) o se in futuro servono richieste range/route dinamiche.
- Costo: un processo in più, ma resta stdlib (nessuna dipendenza).

### Step (con verifica)
1. Scanner `<out>/*/manifest.json` → lista cataloghi (nome, n_shot, durata, detector).
   → verify: trova tutti i film presenti, ignora cartelle senza manifest.
2. Template galleria + `build_index_html` → `<out>/index.html`.
   → verify: card corrette, link che aprono la UI del film giusto.
3. CLI `index` (e/o auto-scrittura a fine `run`) → verify: dopo un run la galleria esiste e si apre.
4. (opz.) Thumbnail primo frame per card → verify: immagini presenti, fallback se manca la clip.

### Tradeoff
- Statico (A) è la scelta minima e coerente; il server (B) va aggiunto **solo se** `file://`
  dà problemi reali — non prima (niente over-engineering).
- Rigenerare la galleria a ogni `run` la tiene aggiornata senza un comando separato; il comando
  `index` esplicito serve per ricostruirla dopo cancellazioni/aggiunte manuali.

---

## Documentation — Tool & dipendenze del progetto

Definizione dei tool su cui si regge la pipeline. `[sistema]` = binario esterno richiesto nel
PATH; gli altri sono pacchetti Python (vedi `pyproject.toml`).

### Runtime di sistema
| Tool | Ruolo nel progetto | Dove |
|---|---|---|
| **ffmpeg** `[sistema]` | Decodifica frame a 48×27 (pipe rgb24) per la detection neurale; estrazione frame per il VLM; taglio delle clip (`copy`/`reencode`). | `detectors/_neural.py`, `caption.py`, `splitter.py` |
| **ffprobe** `[sistema]` | Metadati video (fps, n_frame, durata, risoluzione) → `VideoInfo`. | `io/video.py` |

### Detection (shot boundary)
| Tool | Ruolo | Note |
|---|---|---|
| **TransNetV2** (vendor `soCzech`, MIT) | Detector neurale **primario**; robusto anche su dissolvenze. Gira su **MPS**. | `models/transnetv2.py`, wrapper con windowing 100/50. Pesi convertiti TF→PyTorch. |
| **AutoShot** (vendor `wentaozhu`, CVPR-W 2023) | Seconda opinione neurale (NAS). Gira su **CPU** (op intere non supportate da MPS). | `models/autoshot/`. Pesi solo da Baidu. |
| **PySceneDetect** (`scenedetect`, BSD-3) | Baseline classica content-based (nessun peso). Ottima su hard-cut. | `detectors/pyscenedetect_detector.py` |
| **Ensemble** | `confidence.reconcile` incrocia TransNet+AutoShot: accordo = confidenza, disaccordo = flag. | `confidence.py` |

### ML / numerico
| Tool | Ruolo |
|---|---|
| **PyTorch** (`torch>=2.1`) | Runtime dei modelli neurali; backend **MPS** su Apple Silicon per TransNetV2. |
| **NumPy** (`numpy>=1.24`) | Array dei frame, windowing, `probs_to_ranges`, metriche eval. |
| **einops** (`>=0.7`) | Riarrangiamento tensori nell'architettura AutoShot. |
| **Pillow** (`pillow>=10.0`) | Frame PIL per il VLM (sampling + salvataggio PNG temporanei). |

### ASR (trascrizione dialoghi)
| Tool | Ruolo |
|---|---|
| **faster-whisper** (`>=1.0`) | Trascrizione dialoghi (CTranslate2, CPU int8) con VAD silero. Modello selezionabile a runtime. |

### VLM (descrizione visiva per shot) — Apple Silicon
| Tool | Ruolo |
|---|---|
| **mlx-vlm** (`>=0.1`) | Inference VLM nativa Metal. Modello default: **Qwen2.5-VL-3B-Instruct 4-bit** (`mlx-community`). |

### CLI / UX
| Tool | Ruolo |
|---|---|
| **Typer** (`>=0.12`) | Entrypoint CLI `scene-detector`, parsing flag/opzioni. |
| **tqdm** | Progress bar di ogni fase (decode, inference, split, ASR, VLM). |

### Dev
| Tool | Ruolo |
|---|---|
| **pytest** (`>=8.0`) | Suite unit-test (`tests/`): align, confidence, scene, caption, eval. |

### Extra opzionali (`pip install -e '.[...]'`)
- `neural` → `torch`, `pillow`, `einops` (TransNetV2 / AutoShot)
- `asr` → `faster-whisper`
- `vlm` → `mlx-vlm`, `pillow`
- `dev` → `pytest`
