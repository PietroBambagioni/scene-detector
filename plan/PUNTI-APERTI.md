# Punti aperti ed ecosistema

> Complemento operativo a [UPGRADE.md](UPGRADE.md). Prima parte: cosa resta da fare, con
> l'ordine rivisto dopo le verifiche del 22 luglio 2026. Seconda parte: cosa esiste già di
> pubblico per farlo — stelle, licenza e ultimo aggiornamento presi dall'API di GitHub quel
> giorno, non dai README.

---

## 1 · I punti aperti

| # | Punto | Stato dopo le verifiche | Sforzo | Dipende da |
|---|---|---|---|---|
| **4.4** | Clustering per tracklet | **scritto**, da validare con un run volti | medio | — |
| **2** | Diarizzazione + linking | **molto più economico** del previsto | medio | 4.4 |
| **1** | Scene grouping | **più caro** del previsto, e ora **non risparmia più VLM** | alto | 2º film |
| ~~**3.2**~~ | Media fragments / no cut | ✅ **fatto** come `--split-mode none`, il default resta il taglio | basso | — |
| — | AutoShot: tenerlo o buttarlo | **sospeso in attesa del 2º film** | — | 2º film |
| **3.4** | Ricerca sul catalogo | invariato, rende molto di più dopo la Fase 1 | medio | 1 |
| — | ~~Licenza InsightFace nei crediti~~ | ✅ fatto | minimo | — |
| — | ~~Metriche di valutazione (tolleranza + IoU)~~ | ✅ fatto, resta il ground truth da annotare | medio | — |
| **5** | Setup plug-and-play (`scopo.md`) | **meccanismo fatto**, resta la coda | basso | — |

### 4.4 · Clustering per tracklet — perché è salito in cima

Il run volti su *Anna* (1634 volti, 6,9 min) produce **68 cluster per una decina di presenze
reali**: la protagonista è isolata bene (73 shot), ma altri volti si ripetono in cluster distinti.
Finché una persona è spezzata in tre identità, **qualunque** cosa costruita sopra — nomi dal
dialogo, "chi dice cosa", ricerca per personaggio — eredita la frammentazione.

**Implementato**, ma con un'adattamento che vale la pena spiegare: **ByteTrack non si applica**.
Il tracking per IoU + Kalman presuppone video **denso**; noi campioniamo **6 frame sparsi per
shot** via seek, e fra un campione e l'altro un volto attraversa l'inquadratura — non c'è
continuità geometrica su cui agganciarsi. L'equivalente che regge con frame sparsi è raggruppare
*dentro lo shot* per somiglianza di embedding, tenendo il vincolo che conta.

Quello che c'è ora in `recognition/identify.py`:

- `cluster_within_shot` — greedy dentro un singolo shot con **must-not-link per frame**: due
  volti visti nello stesso fotogramma non possono finire nello stesso gruppo, per quanto si
  somiglino. È il vincolo che impedisce a un campo/controcampo di collassare in un'identità sola.
- `average_embeddings` — un vettore mediato e normalizzato per gruppo. È il passaggio che rende
  robusto il secondo stadio: la media di più viste cancella il rumore di posa e fuoco che fa
  deragliare il singolo frame.
- `cluster_two_stage` — stadio 1 dentro gli shot, stadio 2 sui gruppi mediati, con i gruppi
  grandi come seed invece del singolo volto più nitido. L'interfaccia resta quella di
  `cluster_faces` (un'etichetta per volto), quindi `build_cast` e la gallery non cambiano.
- Pre-filtro `min_face_px=50` (flag `--faces-min-px`) applicato **prima** di clusterizzare.

Blur e yaw non sono stati fatti: richiedono di misurare sull'immagine, e senza un run che dica
se serve sarebbe codice speculativo.

**Validato su *Anna*** (run completo, stessi 373 shot in ensemble). A parità di `min_faces=3` —
la soglia del run originale:

| | cluster | shot coperti |
|---|---|---|
| baseline (per volto) | 68 | 243 |
| **due stadi** | **47** (−31%) | 238 (−2%) |

Regge a ogni soglia: −31% / −19% / −22% di cluster a `min_faces` 3 / 5 / 10, contro −1÷3% di
copertura. È l'esito voluto: **meno identità, stesse persone**. Si vede anche nei cluster grandi —
la protagonista passa da 73 shot/209 volti a **76/262**, il secondo da 44/129 a **51/150**: sono i
frammenti riassorbiti nell'identità principale.

> **Trappola in cui sono cascato leggendo i numeri la prima volta.** Il run nuovo girava col
> default `min_faces=1` e mostrava **230 cluster**: sembrava un peggioramento del 238%. Ma 168 di
> quei 230 hanno **un solo volto** — la baseline li scartava perché usava `min_faces=3`. Confrontare
> conteggi di cluster fra run con `min_faces` diverso non misura niente. È lo stesso genere di
> errore della 0.4: un numero plausibile letto senza la sua condizione.

**Resta aperto:** `min_faces` è ancora un parametro ereditato, non scelto (§3.2), e ora pesa di
più — il due stadi produce molti gruppi da un volto solo, quindi la soglia che li taglia conta.

### 2 · Diarizzazione — cosa è cambiato

Era il punto con due ostacoli (CUDA e modelli gated). Nessuno dei due esiste più: `speech`
(Swift, Homebrew) fa diarizzazione Sortformer in **0,90 s ogni 180 s di audio** sul Neural Engine,
senza token HuggingFace, come binario esterno che non tocca il venv. Ordine: diarizzazione →
linking speaker↔cluster-volto per co-occorrenza → nomi dai vocativi → *poi*, solo se serve
disambiguare, active speaker detection.

Sul linking dei nomi vale la misura fatta sul dialogo di *Anna*: dei 196 candidati "nome proprio",
la maggioranza sono toponimi (Africa, Roma, Germania), falsi positivi grammaticali (Non, Come,
Perché) o **persone citate ma assenti** — `Valpreda` compare 4 volte e non è nel film. I nomi
plausibilmente presenti sono pochi e rari: Anna (7 shot su 373), Roland (5), Vincenzo (4),
Franco (3), Maria (2). Il segnale è sottile: conviene scrivere il nome come **suggerimento con
confidenza** (`name_hint` + score), non sovrascrivere `Personaggio N`.

### Il secondo film — tre misure sospese sullo stesso materiale

*Anna* ha dato tutto quello che poteva: stacchi netti, riprese lunghe, ASL 34 s. Tre decisioni
non sono decidibili su questo film e aspettano il prossimo, possibilmente a montaggio serrato:

1. **AutoShot: tenerlo o rimuoverlo.** Vedi sotto.
2. **Scene grouping (Fase 1): funziona o è solo plausibile?** Con pochi stacchi netti tra riprese
   stabili, qualunque raggruppamento sembra ragionevole. È la stessa trappola della 0.1, dove un
   output plausibile nascondeva metà del parlato distrutto.
3. **OmniShotCut**, ma solo **se** il film ha dissolvenze o fade: è lì che il transition IoU
   3,3× si vede. Su hard cut è già stato misurato pari a TransNet (3 boundary esatti al frame
   su 4) al prezzo di 4× il tempo di detection.

### AutoShot — sospeso, non assolto

Il dubbio è concreto, ma la rimozione aspetta il secondo film.

**Cosa è cambiato sotto i piedi ad AutoShot.** Serviva a produrre la confidenza per accordo
(1.0/0.5). Dopo la 0.4 la confidenza è la prob per-frame di TransNet e non lo tocca più. Gli
restano due funzioni: **aggiungere i boundary che ha visto da solo** (`reconcile`) e riempire
`flags`. La prima è quella sospetta: un boundary visto solo da AutoShot riceve come confidenza
la prob di TransNet a quel frame, cioè **bassa per costruzione** — stiamo aggiungendo tagli in
cui il detector primario non crede. Su *Anna*, **103 boundary su 373 (28%)** non concordati.
In più i due condividono l'input 48×27 e uno spazio NAS derivato da TransNetV2: **errori
correlati**, quindi una seconda opinione che sbaglia dove sbagli tu.

**La misura che deciderà:** TransNet da solo vs ensemble sullo stesso film — quanti shot
esistono *solo* perché AutoShot li ha visti, e sono veri? Quattro minuti di run.

**Se cade:** via `detection/autoshot.py`, `models/autoshot/`, `confidence.reconcile`, i flag CLI,
il registro pesi, i test. Anche 57 MB in meno da scaricare al setup — con `scopo.md` conta.

*Nota: oggi AutoShot non gira quasi mai. Il default è `-d transnet` e l'ensemble è opt-in;
`--all` non lo attiva. Il run di Anna lo usava perché passato a mano.*

### 1 · Scene grouping — perché è sceso, e cosa deve fare

**Decisione presa: le clip per shot restano.** Le scene sono un livello di metadati *sopra* gli
shot, non un rimpiazzo — `scenes: [{index, shots: [i..j], start_time, end_time, description}]`,
nessuna clip di scena su disco (la UI la riproduce come playlist delle sue clip).

**Conseguenza da mettere a verbale: il risparmio VLM sparisce.** Il piano vendeva la Fase 1 come
*«l'unico vero moltiplicatore sul costo VLM»*, ma quel moltiplicatore veniva dal **non** descrivere
più i singoli shot. Se gli shot restano un'unità del catalogo con la sua descrizione, le 373
chiamate restano. Su *Anna*, a 5,5 s/shot: solo shot 34 min · solo scene ~11 min ·
**entrambi 45 min (+32%)**. La Fase 1 quindi **non è più un'ottimizzazione, è una feature**: si
giudica su navigabilità e ricerca, non sul tempo. Resta aperto da dove venga la descrizione di
scena — una chiamata VLM con frame campionati su tutta la scena (vede l'arco, +11 min) oppure
sintetizzata dalle descrizioni degli shot (gratis, ma è un riassunto di riassunti).

**Perché è sceso di priorità**

Il piano raccomandava TranS4mer come "scelta pragmatica". Il repo ufficiale ha
*Pre-trained Models: **TODO*** — nessun checkpoint, flusso pretrain+finetune su CUDA. Adottarlo
significa addestrarlo, esattamente ciò per cui il piano scartava Scene-VLM. Restano BaSSL
(Apache-2.0, ha i pesi, ma CUDA e nessun percorso d'inferenza documentato su un film nuovo),
SceneSeg (ha pesi e tool, **nessuna licenza** — usabile in locale, non vendorabile: §2.7) e il
DIY, che da ripiego diventa piano B serio — e riusa la stessa infrastruttura di embedding della
3.4. Premessa mai verificata del DIY: che **SigLIP giri decentemente su MPS**.

### 3.2 · Media fragments — opzione, non default ✅ **fatto**

Il piano proponeva di **smettere** di tagliare le clip. **Respinto come default:** le clip su
disco restano la normalità. Implementato come **modalità opzionale `--split-mode none`**: salta
il taglio, mette `clip: null` nel manifest e aggiunge `video_src` (path relativo dal catalogo al
film); la UI riproduce l'intervallo con un media fragment `#t=start,end` sul file originale.
Smoke test end-to-end su 60 s di *Rogue One*: nessuna clip su disco, catalogo completo.
Test in `tests/test_manifest.py`.

Serve per il collaudo su un secondo film — costruire il catalogo di *Rogue One* (~2000 shot)
senza duplicare 2,7 GB. Sopravvive anche l'osservazione sull'accuratezza: con `-c copy` i tagli
si allineano ai keyframe, quindi su uno shot corto l'errore pesa in proporzione — se conta,
`reencode` o smart cut.

Indizio emerso per caso dalla diarizzazione: un parlante che **continua attraverso uno stacco**
(Speaker 2 attraversa il taglio a 87,2 s) segnala *stessa scena*. È un segnale diverso dai
"sottotitoli" dell'ablation Scene-VLM — non richiede di capire cosa venga detto — e arriva gratis.
Da misurare.

### 5 · Setup plug-and-play — il requisito che non era nel piano

`scene_detector/scopo.md`: *«una volta fatto il clone si faccia partire con un comando che
permette di scaricare tutte le dependencies e i modelli con i pesi»*. Non compariva né qui né in
UPGRADE.md, ed è trasversale: ogni modello aggiunto da qui in avanti (SigLIP, `speech`,
OmniShotCut) allunga la coda da bonificare alla fine.

**Fatto — il meccanismo.** `core/weights.py` (registro nome → URL + sha256 + destinazione),
`scene-detector-setup` (scarica, verifica l'hash, controlla ffmpeg; `--models` anticipa i ~4 GB
di Whisper/VLM/volti), `install.sh` (venv + `.[all]` + setup), extra `all` in `pyproject.toml`.

**La scoperta che l'ha reso possibile:** entrambi i pesi hanno un mirror pubblico su HuggingFace,
senza auth. `backseollgi/AutoShot` serve `ckpt_0_200_0.pth` **identico byte per byte** al nostro —
il README diceva *«non esiste mirror diretto, l'unica fonte è Baidu»*, ed era falso.
`MiaoshouAI/transnetv2-pytorch-weights` è una conversione diversa (845 byte in più, altra
serializzazione torch) ma con **90/90 tensori uguali**, verificato con `torch.equal`. Non serve
ospitare nulla. Download completo: **8,6 s**.

**Cosa resta:** i modelli grandi restano dietro `--models` e non sono stati collaudati da zero
su una macchina pulita; e nessuno dei tre (Whisper, mlx-vlm, InsightFace) ha un hash verificato —
si fidano del proprio hub.

### Le due cose piccole

~~**Licenza InsightFace**~~ ✅ **fatta.** Il codice è MIT, ma il model package `buffalo_l` è
**solo per ricerca non commerciale**. Nei crediti di OVERVIEW.md stava accanto a "TransNetV2
(MIT)" come se fosse la stessa cosa; ora la distinzione è esplicita.

~~**Metriche**~~ ✅ **fatte** (`evaluation/eval.py`). `evaluate` ora riporta anche `tol` — la
tolleranza viaggia sempre col numero — una `f1_curve` alle tolleranze 0/1/2/5/10, e la metrica
range-based `transition` (IoU sulle transizioni, matching greedy per IoU decrescente).
`transitions_from_ranges` ricava le transizioni dagli shot: contigui = hard cut (i 2 frame a
cavallo), buco = transizione graduale. Test in `tests/test_eval.py`, incluso il caso che
giustifica tutto: dissolvenza di 24 frame, taglio secco nel mezzo → **F1 1,00 · f1_curve tutta a
zero · transition IoU 0,083**.

**Restano due cose, entrambe di dati e non di codice:**
- **il ground truth non esiste.** Le metriche ci sono, non c'è niente da misurare. Bastano ~20
  boundary annotati a mano (§3.4) — e su *Rogue One* vanno annotati anche i **range** delle
  transizioni graduali, o la metrica nuova resta inerte.
- **i volti hanno bisogno di una metrica loro.** Oggi non sapremmo dire se 68 → 15 cluster è un
  miglioramento: serve VPCD (§2.5), non l'IoU sulle transizioni.

---

## 2 · Ecosistema: cosa esiste già

Legenda verdetto: **in uso** · **adottabile** · *riferimento* (da leggere, non da dipendere) ·
⛔ scartato con motivo.

### 2.1 · Shot detection

| Repo | ⭐ | Licenza | Agg. | Verdetto |
|---|---|---|---|---|
| [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) | 5 040 | BSD-3 | 2026-07 | **in uso** |
| [TransNetV2](https://github.com/soCzech/TransNetV2) | 995 | MIT | 2023-12 | **in uso**, non più aggiornato |
| [AutoShot](https://github.com/wentaozhu/AutoShot) | 246 | MIT | 2023-04 | **in uso** |
| [OmniShotCut](https://github.com/UVA-Computer-Vision-Lab/OmniShotCut) | — | MIT | 2026 | **adottabile** — gira su MPS, rimandato a un film con dissolvenze |

### 2.2 · Scene grouping

| Repo | ⭐ | Licenza | Agg. | Verdetto |
|---|---|---|---|---|
| [BaSSL](https://github.com/kakaobrain/bassl) | 142 | Apache-2.0 | 2024-01 | candidato migliore: **ha i pesi** (56,3/57,4 AP MovieNet), ma CUDA e nessun `predict` |
| [SceneSeg / LGSS](https://github.com/AnyiRao/SceneSeg) | 237 | **nessuna** | 2024-05 | pesi + tool d'inferenza; **usabile in locale, non vendorabile** — vedi §2.7 |
| [SCRL](https://github.com/TencentYoutuResearch/SceneSegmentation-SCRL) | 112 | NOASSERTION | 2023-02 | *riferimento* (Tencent, CVPR 2022) |
| [TranS4mer](https://github.com/md-mohaiminul/TranS4mer) | 34 | Apache-2.0 | 2023-06 | ⛔ *Pre-trained Models: TODO* — va addestrato |
| Scene-VLM | — | — | — | ⛔ né codice né pesi |

### 2.3 · ASR e allineamento

| Repo | ⭐ | Licenza | Agg. | Verdetto |
|---|---|---|---|---|
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | 24 454 | MIT | 2025-11 | **in uso** (+ chunking VAD nostro) |
| [WhisperX](https://github.com/m-bain/whisperX) | 23 192 | BSD-2 | 2026-07 | ⛔ misurato: il vantaggio è il chunking, non il modello — e vuole `torch 2.8`/`transformers 4.57` |

### 2.4 · Diarizzazione

| Repo | ⭐ | Licenza | Agg. | Verdetto |
|---|---|---|---|---|
| [speech-swift](https://github.com/soniqo/speech-swift) | 1 073 | Apache-2.0 | 2026-07 | **adottabile** — Swift/Homebrew, Sortformer su Neural Engine, niente token HF |
| [pyannote-audio](https://github.com/pyannote/pyannote-audio) | 10 313 | MIT | 2026-07 | standard di riferimento, ma modelli **gated** |
| [FunCineForge](https://github.com/FunAudioLLM/FunCineForge) | 442 | Apache-2.0 | 2026-03 | *riferimento* per l'active speaker detection (CUDA, nasce per dataset di doppiaggio) |
| [TranscriptionSuite](https://github.com/homelab-00/TranscriptionSuite) | 611 | GPL-3.0 | 2026-07 | *riferimento* — GPL, attenzione |

### 2.5 · Volti e riconoscimento personaggi

| Repo | ⭐ | Licenza | Agg. | Verdetto |
|---|---|---|---|---|
| [InsightFace](https://github.com/deepinsight/insightface) | 29 307 | codice MIT, **model package a licenza separata** | 2026-07 | **in uso** |
| [ByteTrack](https://github.com/FoundationVision/ByteTrack) | 6 570 | MIT | 2024-06 | **adottabile** per la 4.4 — IoU + Kalman, nessuna CUDA nel tracker |
| [vectornguyen76/face-recognition](https://github.com/vectornguyen76/face-recognition) | 199 | MIT | 2024-10 | *riferimento* — SCRFD + ArcFace + ByteTrack, il nostro stack esatto |
| [pyannote-video](https://github.com/pyannote/pyannote-video) | 476 | MIT | 2024-03 | *riferimento* — detection → tracking → clustering |
| [BoT-FaceSORT](https://github.com/bellhyeon/BoT-FaceSORT) | 6 | MIT | 2025-06 | *riferimento* (ACCV'24), multi-face tracking robusto |
| [Video_Person_Clustering](https://github.com/Andrew-Brown1/Video_Person_Clustering) | 55 | MIT | 2022-05 | **dataset + metriche** (VPCD, VGG): 35 396 face-track su 23 h |
| [BallClustering](https://github.com/makarandtapaswi/BallClustering_ICCV2019) | 99 | **nessuna** | 2020-04 | risolve il nostro problema esatto (n. cluster ignoto) ma non è riusabile |

### 2.6 · VLM e ricerca sul catalogo

| Repo | ⭐ | Licenza | Agg. | Verdetto |
|---|---|---|---|---|
| [mlx-vlm](https://github.com/Blaizzy/mlx-vlm) | 5 234 | MIT | 2026-07 | **in uso** |
| [faiss](https://github.com/facebookresearch/faiss) | 40 566 | MIT | 2026-07 | **adottabile** per la 3.4 |
| [open_clip](https://github.com/mlfoundations/open_clip) | 14 013 | NOASSERTION | 2026-07 | **adottabile** (SigLIP) |
| [clip-retrieval](https://github.com/rom1504/clip-retrieval) | 2 788 | MIT | 2026-03 | *riferimento* |
| [VideoHighlighter](https://github.com/Aseiel/VideoHighlighter) | 59 | **AGPL-3.0** | 2026-07 | *riferimento* — licenza contagiosa |
| [video-caption](https://github.com/MarcinDudekDev/video-caption) | 4 | MIT | 2026-03 | *riferimento* — stack simile (mlx-vlm + Whisper) |

### 2.7 · Attenzione alle licenze

Tre repo utili **non hanno licenza** (SceneSeg, BallClustering, e in parte SCRL/open_clip come
`NOASSERTION`): senza licenza il default è "tutti i diritti riservati", e i ToS di GitHub
concedono solo *view* e *fork*.

**Ma la domanda giusta non è se il repo è libero: è cosa ne facciamo.** Il README di SceneSeg
dice esplicitamente *«since some enthusiastic researchers are requesting the codes … we release
an on-going version here»* — intento di condivisione dichiarato. Questo copre l'uso **locale**
(scaricarlo, farlo girare, valutarlo, tenerlo nella propria pipeline): rischio pratico nullo.
Non copre la **ridistribuzione**, cioè il vendoring nel nostro repo — che è invece quello che
facciamo oggi con TransNetV2 e AutoShot in `detection/models/`.

Da qui la regola operativa: **codice senza licenza si scarica al setup, non si vendora.** È lo
stesso schema già usato per i pesi in `core/weights.py`: il file arriva dalla fonte originale
sulla macchina di chi installa, noi ridistribuiamo zero. Vale per SceneSeg e BallClustering.
Aprire una issue chiedendo agli autori di aggiungere una licenza costa nulla e chiuderebbe
la questione alla radice.

Altri sono **GPL-3.0**
(TranscriptionSuite) o **AGPL-3.0** (VideoHighlighter): copiarne codice cambierebbe la licenza del
progetto. I candidati puliti sono BaSSL, speech-swift, FunCineForge (Apache-2.0), WhisperX
(BSD-2), ByteTrack, VPCD, mlx-vlm, faiss (MIT).

### 2.8 · Cosa non esiste

Nessuna pipeline locale su Apple Silicon che vada da shot → scene → VLM → ASR → volti → catalogo
navigabile. I pezzi esistono tutti separatamente; l'integrazione su MLX e lo **scene grouping**
non compaiono in nessuno dei progetti trovati.

---

## 3 · Fili lasciati aperti

Cose emerse durante i collaudi e non ancora approfondite. Nessuna è bloccante; diverse sono
economiche e alcune potrebbero far risparmiare lavoro già messo in preventivo.

### 3.1 · ASR

- **`word_timestamps=True` esiste già in faster-whisper.** WhisperX e `speech align` sono stati
  valutati per i word timestamps senza prima controllare il backend che usiamo: il parametro c'è
  (default `False`). Se la qualità regge, il punto 2.3 del piano si chiude con **un flag**, senza
  binari esterni né allineatori. **Da misurare per primo**, prima di cablare `speech align`.
- **`hallucination_silence_threshold` non è mai stato considerato.** La 0.1 elenca
  `no_speech_threshold` e `compression_ratio_threshold`, ma faster-whisper espone anche questo
  parametro dedicato, che salta il silenzio quando sospetta un'allucinazione. Da provare insieme
  al chunking.
- **La verifica sul film intero è sospesa.** Il loop `"non ti puoi parlare"` ×3 nasce sulla lunga
  distanza: su 180 s isolati non si riproduce nemmeno senza chunking. Solo un run completo
  (~48 min stimati) dice se il chunking lo elimina davvero.
- **Il primo tentativo di run completo ha trovato un bug diverso, e peggiore.** Il ramo `vad=True`
  rilevava la lingua su `wm.detect_language(audio)`, cioè sull'audio **grezzo**. I primi 30 s di
  *Anna* sono un cartello muto: Whisper ha risposto **`en` (p=0,62, tirava a indovinare)** e ha
  trascritto **tutto il film in inglese** — *«because I'm not an alphabet, I'm not even a
  creditor»*. Il ramo vecchio non aveva il problema perché `wm.transcribe(path)` con VAD rileva
  dopo aver isolato il parlato. **Fix:** `speech_head(audio, windows)` concatena i primi 30 s di
  *parlato* dalle finestre VAD e rileva su quelli → **`it` p=0,99**, verificato sui primi 5 min
  di *Anna*. Un bug che avrebbe corrotto in silenzio ogni catalogo di film non inglese che non
  apre parlando: è precisamente il tipo di difetto che solo la validazione sul film intero trova.
- **Il run completo va rifatto**, per due motivi indipendenti: il contenuto era in lingua sbagliata
  e la macchina era occupata da una videochiamata, quindi anche i 60,7 min di parete non valgono
  come confronto coi 41 min della baseline. Serve un run a macchina libera.
- **Due parametri scelti, non ottimizzati.** `MAX_WINDOW_S = 30` (finestra nativa di Whisper) e
  `min_silence_duration_ms = 500`. Il prototipo, con finestre fino a 49 s, dava lo stesso
  risultato: il valore migliore sta in un intervallo, non in un punto. Vale una piccola griglia.
- **`speech denoise` / `restore` mai provati.** Il restauro 2011 di *Anna* ha **volutamente
  conservato** fruscio e ronzio del magnetico — cioè il substrato esatto su cui Whisper allucina.
  Ripulire l'audio *a monte* dell'ASR è l'intervento più diretto sulla causa, e non l'abbiamo
  toccato.
- **`speech transcribe`** (Qwen3-ASR, Parakeet-TDT) non è stato confrontato con faster-whisper:
  sarebbe ASR nativo su Neural Engine.

### 3.2 · Volti

- **Il problema potrebbe non essere solo la purezza dei cluster, ma il *recall*.** 1634 volti su
  3h33m sono pochissimi: molte presenze non vengono viste affatto. La 4.4 punta a ridurre i falsi
  cluster, ma non recupera chi non è mai stato rilevato. È il motivo per cui VPCD usa anche i
  **body-track** — su un film osservativo, con gente di spalle e in penombra, pesa più che su una
  sitcom.
- **`min_faces`**: il run ha usato 3 (il default della funzione è 1). Cambia direttamente il numero
  di cluster nel cast — va scelto, non ereditato.
- **Il provino del cast è stato lo strumento diagnostico migliore** di tutta la sessione: una
  contact sheet dei cluster maggiori ha reso evidente in un colpo d'occhio la frammentazione.
  Varrebbe la pena renderlo un output stabile della pipeline, non uno script usa-e-getta.

### 3.3 · VLM

- ~~**L'ancora b/n (0.2) potrebbe essere diventata superflua.**~~ ✅ **A/B fatto → rimossa.**
  Stessi 35 shot, stessi frame, greedy, unica variabile il flag: **0/35 menzioni di colore con
  l'ancora e 0/35 senza**; il modello dichiara il b/n da sé in 23 casi su 35 anche senza
  istruzione. In più la giustificazione per tenerla era falsa: si teneva come rete per lo shot 0,
  ma quel cartello è testo chiaro su fondo e `_is_grayscale` lo classificava *a colori* — l'ancora
  non si attivava mai proprio lì. Via `_is_grayscale`, il ramo di `build_prompt`, 2 test.
  Dati in `prove/vlm-ab/ab_ancora_bn.json`.
- ~~**La deriva narrativa si combatte nel prompt.**~~ ✅ **fatto** — `build_prompt` ora marca il
  dialogo come *«solo contesto»* e aggiunge *«non ripeterlo né parafrasarlo»*. **Da misurare:**
  l'effetto sulla deriva (1,4% sull'8B-4bit, 6,2% sul 4B) non è stato verificato — la modifica è
  ragionata, non collaudata.
- ~~**`temperature=0.3` in produzione.**~~ ✅ **portata a `0.0`.** Per un catalogo la
  riproducibilità vale più della varietà, e tutti i confronti fra modelli erano già in greedy:
  il default di produzione ora coincide con le condizioni in cui l'8B-4bit è stato scelto.
- **`max_tokens=128` è un limite arbitrario**: troncava 3 descrizioni su 36 col 4B (nessuna con
  l'8B-4bit, che è più conciso). Se un giorno si torna a un modello verboso, il limite morde.
- **I cartelli non sono scene** — *promosso: è il residuo vero della 0.2*. Shot 0 e shot 3 sono
  testo su fondo (avviso al pubblico, nota di restauro): il VLM li descrive come inquadrature, e
  sono i due casi su cui il 4B ha fabbricato di più. Un catalogo dovrebbe marcarli come
  *non-scena*. **Il segnale che c'era è stato appena rimosso**: erano gli unici shot con
  `grayscale=False` in un film b/n, cioè "chroma alta su film monocromo" li isolava gratis.
  Se si affronta il punto, quel test va riscritto per quello che è — un rilevatore di cartelli,
  non un'ancora di prompt.

### 3.4 · Shot detection e transizioni

- **Le etichette di transizione di OmniShotCut sarebbero metadati nuovi**: `Dissolve`, `Wipes`,
  `Fade`, `Zoom`, `Slide`, `Push`, `Doorway` per l'intra-shot; `Hard_Cut`, `Transition`,
  `Sudden_Jump` per l'inter-shot. Oggi il manifest sa *dove* taglia, non *come*.
- **`Sudden_Jump` merita attenzione su questo film.** Il paper dichiara di cogliere
  "discontinuità sottili ma dannose": *Anna* è girato con un Portapak, dove ogni pausa macchina
  lascia uno scarto che non è un montaggio ma nemmeno continuità. Nessuno dei nostri detector lo
  modella.
- **Manca un ground truth.** Il confronto OmniShotCut ↔ manifest assume che il manifest abbia
  ragione. Sui 4 stacchi netti coincidono al frame, quindi poco importa; ma sul punto contestato
  (frame 2270-2294) **non sappiamo chi ha ragione**, e senza annotazione manuale non lo sapremo.
  Bastano una ventina di boundary annotati a mano per avere un metro.

### 3.5 · Diarizzazione

- **Sortformer sarebbe limitato a ~4 parlanti** (riportato dalla documentazione di terze parti,
  non verificato). Sul segmento provato ne ha trovati 3. Su un film corale con scene di gruppo il
  limite conta: da verificare prima di adottarlo per l'intero film, e confrontare con gli engine
  alternativi (`pyannote`, `community1`) che `speech` offre comunque.
- **`speech embed-speaker` è la via diretta al linking voce↔volto**: estrae un embedding del
  parlante, quindi si può costruire una *gallery vocale* per personaggio e legarla ai cluster di
  volti per co-occorrenza — più solido che passare per i nomi nel dialogo.

### 3.6 · Infrastruttura

- **Il nucleo di verità della 3.1, mai raccolto**: quando `--faces` e `--vlm` girano insieme
  campionano **gli stessi shot** in modo indipendente (6 seek a 640 px + 3 seek a 512 px).
  Condividere i frame vale ~2-3 minuti a film. Piccolo, opportunistico, ma è l'unica parte della
  3.1 che sopravvive alla verifica.
- **OmniShotCut vuole 128×96, noi decodifichiamo 48×27.** Se un giorno lo si adotta, il decode
  condiviso della detection va rifatto a risoluzione diversa: non è drop-in.
- **SigLIP su MLX è da verificare.** Il DIY per la Fase 1 (embedding per shot + clustering con
  vincolo temporale) presuppone che SigLIP giri decentemente su questo hardware. Non è stato
  provato, ed è la premessa del piano B.

---

## 4 · Paper di riferimento

Il nostro problema "chi parla e chi è" ha un nome in letteratura: *character-aware subtitling* /
*speaker naming in movies*.

- **[Character-aware audio-visual subtitling in context](https://arxiv.org/pdf/2410.11068)** —
  Huh & Zisserman (VGG Oxford, 2024). ASR + diarizzazione + riconoscimento personaggi + un LLM che
  ragiona sul contesto temporale. È il design più vicino a quello che serve a noi.
- [Face, Body, Voice: Video Person-Clustering with Multiple Modalities](https://arxiv.org/pdf/2105.09939) —
  Brown, Kalogeiton, Zisserman (ICCVW 2021). Il **corpo** identifica quando il volto non è
  visibile: rilevante su un film osservativo come *Anna*, dove 1634 volti su 3h33m sono pochi.
- [Speaker Naming in Movies](https://arxiv.org/pdf/1809.08761) ·
  [Deep Multimodal Speaker Naming](https://arxiv.org/pdf/1507.04831) — i lavori fondativi.
- [ScreenWriter](https://arxiv.org/pdf/2410.19809) — genera sceneggiature da video, nomina i
  personaggi con clustering a grafo.
- [OmniShotCut](https://arxiv.org/abs/2604.24762) (2026) · [TranS4mer](https://arxiv.org/abs/2212.14427) (CVPR 2023).
