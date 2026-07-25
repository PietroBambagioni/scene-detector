# Da fare — tutto ciò che resta aperto

> Indice unico dei punti aperti, raccolti da UPGRADE.md, PUNTI-APERTI.md, TRANSIZIONI-GRADUALI.md
> e le due SESSIONE. **Qui c'è la lista; il dettaglio e i numeri stanno nei doc citati.** Aggiornato
> il 24 luglio 2026.
>
> Legenda: 🔴 azionabile ora · 🟡 dipende da altro · 🔵 opportunistico/piccolo · ⛔ deciso, non si fa

---

## 0 · Immediato

- [ ] 🔴 **Committare** il fix volti (`--faces-min-shots`, ora **default 3**) + il fix UI (seek su
  `currentTime`) — i 9 file di [SESSIONE-2026-07-24 §8](SESSIONE-2026-07-24.md). 86 test verdi.
- [x] **Default `faces-min-shots`** scelto: **3** (65 personaggi su *Rogue One*). `config.py` + `cli.py`.
- [x] **AutoShot — buttato.** Due annotatori ciechi su 40 boundary di *Rogue One* (`prove/annota/`):
  i boundary unici di AutoShot sono stacchi veri nel 67% (Claude) / 40% (Pietro) dei casi contro il
  80% / 73% di TransNet — non paga il +52% di tempo. Rimosso: `detection/models/autoshot/`,
  `confidence.py` (reconcile), `--ensemble`/`--autoshot-weights`, `DetectorKind.autoshot`, registro
  pesi, `einops`, `test_confidence.py`. −922 righe, 82 test verdi. Chiude "AutoShot: tenerlo o
  buttarlo". Resta su disco `weights/autoshot.pth` (57 MB, gitignored, non più scaricato).
- [ ] 🔵 **README §Valutazione stale** — cita `evaluate`/`read_scenes_txt`/`f1_curve`, rimossi in
  `40a7d06`. Riscrivere sull'API vera (`prf1(tol)` + `transition_iou`).

---

## 1 · Detection & transizioni

- [ ] 🟡 **OmniShotCut in pipeline.** Misurato complementare, non sostitutivo: union corse+Omni
  porta il recall 0,215 → 0,534 ([TRANSIZIONI-GRADUALI §5.15](TRANSIZIONI-GRADUALI.md)). **Serve
  materiale con dissolvenze** — *Rogue One* ne ha 5 sopra i 10 frame. Dipende da: un film con
  graduali + `reconcile` riscritta su **range** (oggi lavora su boundary puntuali) + una dep nuova
  (venv separato, 128×96 invece del nostro 48×27).
- [ ] 🔵 **Etichette di transizione come metadati.** Omni tipizza (`Dissolve`/`Fade`/`Wipe`/…): oggi
  il manifest sa *dove* taglia, non *come*. Arriva gratis se si adotta Omni.
- [ ] 🔵 **`Sudden_Jump`** — scarti da pausa-macchina (Portapak di *Anna*), nessun detector li
  modella. Da valutare solo su quel tipo di materiale.
- [ ] 🔵 **GT boundary manuale** — ~20 boundary annotati a mano darebbero un metro dove oggi si
  assume che il manifest abbia ragione.

---

## 2 · Volti

- [ ] 🟡 **Frammentazione 22↔85** (coseno 0,764, stesso volto in due cluster). Il greedy a passo
  singolo non li fonde: serve un secondo merge sui centroidi finali. Un caso su *Rogue One*, forse
  più su altri film.
- [ ] 🔴 **Metrica di purezza (VPCD).** Il 68→47 / 661→113 sono conteggi di cluster, non purezza.
  Dataset+metriche in [PUNTI-APERTI §2.5](PUNTI-APERTI.md) (Video_Person_Clustering, MIT).
- [ ] 🔵 **Recall, non solo purezza.** 1634 volti su 3h33m di *Anna* sono pochi: molte presenze mai
  viste. La 4.4 riduce i falsi cluster ma non recupera chi non è mai stato rilevato — VPCD usa i
  **body-track** per questo.
- [ ] 🔵 **Provino del cast come output stabile** — la contact-sheet dei cluster è stata lo strumento
  diagnostico migliore; oggi è uno script usa-e-getta.

---

## 3 · ASR

- [ ] 🔴 **Run ASR completo su *Anna* a macchina libera** — l'unica cosa in stato **indeterminato**:
  i due tentativi sono stati annullati (bug lingua + macchina contesa). Serve per validare il
  chunking VAD sul film intero.
- [ ] 🔵 **`word_timestamps=True`** già in faster-whisper (default `False`): da misurare **prima** di
  cablare `speech align`. Se regge, chiude la 2.3 con un flag.
- [ ] 🔵 **`hallucination_silence_threshold`** mai provato — parametro dedicato di faster-whisper.
- [ ] 🔵 **`speech denoise`/`restore`** mai provati — il restauro di *Anna* ha conservato fruscio e
  ronzio, cioè il substrato su cui Whisper allucina. Intervento a monte dell'ASR.
- [ ] 🔵 **`MAX_WINDOW_S=30` e `min_silence_duration_ms=500`** scelti, non ottimizzati. Vale una
  piccola griglia.

---

## 4 · VLM

- [ ] 🔵 **Cartelli non sono scene** — shot di solo testo (avvisi, note di restauro) descritti come
  inquadrature. Un catalogo dovrebbe marcarli *non-scena*. Il segnale gratis (`_is_grayscale`) è
  stato rimosso: il rilevatore va riscritto per quello che è.
- [ ] 🔵 **`max_tokens=128`** arbitrario: non morde con l'8B-4bit (conciso), morderebbe con un
  modello verboso.
- [ ] 🔵 **Deriva narrativa nel prompt** — la marcatura "dialogo = solo contesto" è ragionata, non
  misurata.

---

## 5 · Feature nuove (Fase 1 / 2 / 3.4)

- [x] **Scene grouping (Fase 1) — implementato, non ancora giudicato.** `scene_detector/grouping.py`,
  flag `--scenes` / `--n-scenes`, chiave `scenes` nel manifest (`first_shot`/`last_shot` inclusivi),
  8 test sintetici. Nessuna clip di scena su disco, nessuna descrizione: si aggiunge dopo la misura.
  - **Né SigLIP né BaSSL: Optimal Sequential Grouping** (Rotman/Porat/Ashour 2016, riferimento MIT
    [ivi-ru/video-scene-detection](https://github.com/ivi-ru/video-scene-detection)). DP sulla
    matrice di distanze fra shot, **non addestrato, zero dipendenze nuove, zero pesi** — e la
    contiguità temporale è *nella formulazione*, non un vincolo aggiunto dopo. Il DIY prevedeva
    "clustering con vincolo temporale": OSG è quel vincolo fatto bene. La premessa "SigLIP su MPS"
    resta non verificata e **non serve più verificarla per partire**: OSG è agnostico alle feature,
    SigLIP entra sostituendo `shot_signatures` e nient'altro.
  - **Firme = istogrammi HSV sui frame 48×27** che il detector legge già (stessa risoluzione del
    `ColorHistograms` interno di TransNetV2). Il segnale più povero possibile, deliberatamente.
  - **Misurato su *Rogue One*** (3204 shot, 192 701 frame): decode 47 s · firme+distanze 2 s ·
    DP 17 s. **k stimato 126** dal gomito dei valori singolari, 25,4 shot/scena, mediana 41 s.
    Contiguo e completo.
  - ⛔ **Il correttivo della punteggiatura è stato provato e tolto.** Il manuale (r. 1251) dà
    dissolvenza/tendina/iris come marcatori di blocco narrativo e `Scene.transition` sembrava
    offrirli gratis. Due misure indipendenti dicono di no. **Una**: dei 461 `transition` di
    *Rogue One* **279 sono da 2 frame**, cioè stacchi netti per costruzione (una corsa `i..j`
    diventa `(i, j+1)`); solo 35 arrivano a ≥6. **Due**: nell'annotazione cieca i confini forzati
    da quelle 35 — comprese una da **10** e una da **13** frame, cioè la fascia che DA-FARE
    chiamava "dissolvenze" — sono stati giudicati **0/7 cambi di scena**, *sotto* il 15% dei
    controlli casuali. Il campo dice dove il detector ha visto una corsa calda, non che lì ci sia
    una dissolvenza. Riaprire solo con un detector che **tipizza** le transizioni (§1, OmniShotCut).

  ### Il verdetto dell'annotazione cieca — 38%, contro una soglia di 70%

  33 confini proposti + 33 non-confini giudicati (4 "non so"), annotatore singolo, `key.json`
  nascosto. `prove/scene_ab.py --verdict`:

  | popolazione | n | giudicati "scena diversa" |
  |---|---|---|
  | confini da sola OSG | 26 | **10 = 38%** |
  | confini forzati dalla punteggiatura | 7 | **0 = 0%** |
  | non-confini (controllo casuale) | 33 | 5 = 15% |

  **Il segnale visivo esiste** — 38% contro 15% è Fisher a una coda **p = 0,041**, non rumore —
  **ed è troppo debole**. Per il criterio fissato *prima* di misurare (≥70%) la conclusione è
  quella pre-registrata: **le feature non bastano**, non "si ritocca k". Prossimo passo SigLIP,
  che entra sostituendo `shot_signatures` e nient'altro.

  ### Fase 1b — SigLIP misurato su RAI: non cambia niente (p = 0,68)

  **Il banco non ha più bisogno di un umano.** Il GT di scena era già su disco:
  `prove/rai/RAIDataset/`, 10 video Rai Scuola, **116 confini annotati da esperti**, range
  `start end` — lo stesso formato dei nostri gruppi. Il caveat di `prove/rai_ab.py:11` («su RAI la
  precision non si misura») vale perché lì si predicevano *shot* contro un GT di *scene*: qui
  pred e GT sono lo stesso oggetto, quindi P/R/F1 sono legittimi. `prove/rai_scene_ab.py`,
  k = |GT| per video (si misurano le feature, non la stima di k).

  | metodo | F1 @tol 5 | F1 @tol 25 |
  |---|---|---|
  | soffitto del detector (recall) | 0,888 | 0,983 |
  | casuale (20 seed) | 0,094 | 0,126 |
  | uniforme | 0,095 | 0,103 |
  | **istogrammi HSV** | **0,259** | **0,328** |
  | **SigLIP centrato** | **0,284** | **0,353** |

  - **SigLIP non batte gli istogrammi.** 33 confini trovati contro 30 su 116; McNemar esatto sui
    discordanti **p = 0,68** (tol 5) e **0,70** (tol 25). Tre confini di scarto: rumore.
  - **Il segnale però c'è**: entrambi stanno a 2,7-3,5× il casuale, e l'uniforme non stacca il
    casuale (le scene RAI non sono equispaziate, quindi il banco non è vincibile a caso).
  - **Non è colpa della detection**: il soffitto è 0,89 di recall a tol 5 e 0,98 a tol 25. Gli
    shot ci sono; è il raggruppamento che non li usa bene.
  - **SigLIP è anisotropo**, come sospettato dal probe (coseno 0,993 intra contro 0,934 inter su
    rumore): togliere la media vale **+0,034** di F1 su SigLIP e **−0,018** sugli istogrammi.
  - ✅ **La premessa mai verificata è verificata**: `siglip2-base-patch16-224` gira su MPS a
    **104 img/s** (`prove/siglip_mps.py`). End-to-end però si scende a **13-15 img/s**, perché il
    collo di bottiglia sono i 3 seek ffmpeg per shot, non l'inferenza.
  - Gotcha `transformers` 5.x: `get_image_features` torna un `BaseModelOutputWithPooling`, non un
    tensore. Serve `.pooler_output`.

  **La conclusione che conta.** Due famiglie di feature lontanissime per potere semantico —
  istogrammi di colore e un encoder vision-language — cadono **dentro il rumore l'una dall'altra**
  a 0,26-0,35 di F1. Il tetto non è nella rappresentazione, è **nel metodo**: OSG su una matrice
  di distanze non modella cosa tiene insieme una scena. Il che rende la scelta pre-registrata
  (**BaSSL**) quella giusta anche per diagnosi e non solo per protocollo: non è un'altra feature
  da infilare in OSG, è un modello addestrato che i confini li predice lui.

  **`siglip_signatures` + `transformers` nell'extra `neural` restano** (deciso, 25 lug 2026):
  hanno perso la misura ma non sono cancellati, perché BaSSL potrebbe volere un encoder e
  rifarli costerebbe più che tenerli. **Non sono nel percorso della pipeline** — `pipeline.py`
  chiama `shot_signatures`. Se BaSSL non li usa, si cancellano allora.

  ### Fase 1c — BaSSL è chiuso, e il metodo conta più delle feature

  ⛔ **BaSSL non è adottabile senza addestrarlo.** Dal Model Zoo, verbatim: «We provide
  pre-trained checkpoints trained in a **self-supervised** manner. **After fine-tuning** with the
  checkpoints, the models will give scores…». Tutti e cinque i checkpoint (SimCLR ×3, BaSSL 10 e
  40 epoch) sono pre-training: adottarlo significa **finetunare su MovieNet-SSeg**, cioè
  esattamente il criterio con cui erano stati scartati TranS4mer e Scene-VLM (UPGRADE §Fase 1).
  In più: `pytorch==1.7.1+cu110`, `pytorch-lightning==1.3.8`, CUDA 11.0, e nessun percorso di
  inferenza documentato. **Chiude con un no** la domanda aperta «se i pesi pubblicati siano quelli
  finetuned o solo i self-supervised».

  ⛔ **OVSD non è più scaricabile.** `research.ibm.com/haifa/projects/imt/video/…` → **404**,
  nessun mirror delle annotazioni (la ricerca trova solo Open vSwitch e l'istruzione `movsd`). I
  video sono CC e si troverebbero, le annotazioni no. **RAI resta l'unico banco: 116 confini, ed
  è il tetto di quello che possiamo misurare.**

  **Il costo di OSG conta più delle feature** (`prove/osg_variants.py`, firme in cache, secondi):

  | variante | hsv @5 | hsv @25 | siglip @5 | siglip @25 |
  |---|---|---|---|---|
  | H_add (quella in uso) | 0,259 | 0,328 | 0,284 | 0,353 |
  | **H_add banda 5** | **0,310** | **0,388** | 0,276 | 0,336 |
  | H_add banda 10 | 0,276 | 0,345 | 0,276 | 0,345 |
  | H_add banda 20 | 0,259 | 0,328 | 0,284 | 0,353 |
  | H_nrm | 0,276 | 0,345 | 0,302 | 0,379 |
  | H_nrm banda 10 | 0,086 | 0,103 | 0,103 | 0,112 |

  `H_add` somma **tutte** le distanze dentro un blocco: una scena di 40 shot viene penalizzata
  perché lo shot 1 non somiglia al 40. Le scene vere derivano. Bandare a W shot toglie quel prior
  globale. Il risultato migliore di tutta la campagna — **0,388** — arriva così, con gli
  istogrammi poveri, battendo SigLIP.

  Su RAI da solo **non era stabilito**: McNemar p = 0,18 (tol 5) e 0,092 (tol 25), casella scelta
  post-hoc fra 24. Il secondo banco lo ha confermato — vedi sotto.

  ### Fase 1d — il secondo banco: BBC Planet Earth, e finalmente si sa cos'è un buon punteggio

  ✅ **Trovato ed è meglio di RAI.** `prove/bbc_scene_ab.py`: 11 episodi, **4855 shot ground
  truth**, **5 annotatori**, 2745 confini (5,8× RAI). Annotazioni da AImageLab (stesso laboratorio
  di RAI), video su MediaFire dal readme del dataset — 4,8 GB. Allineamento verificato prima di
  misurare: lo scarto fra ultimo frame annotato e fine video è 0-30 frame su episodi da 50 minuti.
  Due proprietà che RAI non ha:

  - **gli shot sono ground truth**, quindi si misura il *raggruppamento* senza il soffitto della
    detection (su RAI era 0,89 di recall a tol 5);
  - confini e predizioni in **indici di shot**, non in frame: niente tolleranza da citare.

  🎯 **Il numero che mancava a tutta la campagna: l'accordo fra umani.** Dalle sole annotazioni,
  senza nemmeno i video — F1 mediana fra coppie di annotatori **0,630** (min 0,461, max 0,678, 10
  coppie). E i cinque marcano da **327 a 706** confini sugli stessi 11 episodi: **2,2× di scarto su
  quante scene ci siano**. Conseguenze:

  - **il bersaglio non è F1 1,00, è ~0,63.** Ogni numero di questo progetto va letto come frazione
    di quello.
  - «non sono un esperto di cinema e potrei sbagliare» era **giustificato e non era il problema**:
    gli esperti fra loro stanno a 0,63.
  - la stima automatica di k non fallisce solo per debolezza dell'euristica: **un k vero non
    esiste**, gli annotatori differiscono di 2,2×.

  ✅ **La banda è confermata** (`prove/bbc_scene_ab.py`, k = |scene dell'annotatore|):

  | variante | mediana sui 5 annotatori | % dell'accordo umano |
  |---|---|---|
  | H_add senza banda | 0,242 | 38% |
  | banda 2 | 0,303 | 48% |
  | **banda 3** | **0,317** | **50%** |
  | banda 5 (in uso) | 0,300 | 48% |
  | banda 8 | 0,287 | 46% |
  | banda 15 | 0,260 | 41% |

  Migliorano **tutti e cinque** gli annotatori; McNemar appaiato senza banda vs W=5 dà
  **p < 0,01 su 4 su 5** (ann2: p = 0,44, stessa direzione). Curva unimodale su entrambi i banchi,
  che si appiattisce quando W supera la scena media: è il meccanismo atteso, non un picco casuale.

  **W=5 resta** e non passa a 3: 3 vince su BBC di 0,017 ma su RAI ricade esattamente sul valore
  di «nessuna banda» (−0,060). 5 è ottimo su un banco e a un soffio sull'altro.

  ⚠️ **Trappola in cui sono caduto, per chi rifà le misure**: dopo aver messo `BAND=5` come default
  in `optimal_sequence`, il banco che pre-bandava la matrice ri-bandava sopra il default — bande
  5, 10, 20 e «nessuna banda» davano tutte lo **stesso** numero. Il segnale era proprio quello:
  righe diverse con F1 identico byte per byte. La banda va passata esplicita, non applicata al dato.

  **Dove siamo, in una riga**: 0,300-0,317 di F1, cioè **circa metà dell'accordo fra annotatori
  esperti**, con feature che sono istogrammi di colore su frame 48×27 e zero modelli addestrati.

  ⛔ **`--scenes` resta fuori da `--all`** (deciso, 25 lug 2026). Non per il costo — una
  decodifica in più, 47 s su un film di 2 h, niente accanto ai 45 min di ASR+VLM. È che `--all`
  non può passare `--n-scenes`, e senza quello la stima sbaglia di ~40%: sarebbe spedire scene
  note-sbagliate a chiunque scriva `--all`. Rientra quando la stima di k funziona, o quando la UI
  le rende ispezionabili.

  **Resta aperto, ed è l'unica cosa che rende le scene utili**: 🔴 **UI a tre livelli**
  (`catalog/ui.py:120,136`, il pattern `charFilter:91` è il modello). `scenes` nel manifest non
  serve a nessuno finché la galleria non lo mostra, e i confini ora sono buoni abbastanza da
  impaginarli.

  ⛔ **La stima di k non funziona** (`--estimate`). Contro il numero vero di scene per video, il
  gomito dei valori singolari sottostima sistematicamente: media 7,2 (HSV) e 10,0 (SigLIP) contro
  **12,6** reale, e non segue il video (GT 22 → 5; GT 5 → 7). Conseguenza retroattiva: i **126**
  di *Rogue One* sono con ogni probabilità una forte sottostima. Chi usa `--scenes` sul serio
  dovrebbe passare `--n-scenes`.

  ### Bug trovato dal banco — `sample_frames` campionava fuori dallo shot

  Non del grouping, e già in produzione: `_timestamps` rientrava di `min(0,15·dur, 0,3)`, che su
  uno shot da 5 frame a 25 fps vale **0,03 s — meno di un frame**. `end_time` è esclusivo
  (`(end_frame+1)/fps`), quindi l'ultimo istante cadeva oltre il PTS dell'ultimo frame: ffmpeg,
  che con `-ss` prende il primo frame *a partire da* t, tornava **il primo frame dello shot
  successivo** — o niente, a fine file (è così che si è manifestato: crash sull'ultimo shot del
  video 9). Colpiva `faces` e `vlm`, non solo il grouping: **2,2% degli shot di *Rogue One***
  (71 su 3204), 0% su *Anna*. Corretto in `captioning/caption.py` con il tetto `end − 1/fps`,
  `fps` propagato dai tre chiamanti, 2 test nuovi.

  **Due limiti del banco precedente (annotazione umana), per non ripeterli:**
  - **Manca un controllo positivo.** Il protocollo AutoShot ne aveva uno (i boundary su cui i due
    detector concordavano = tagli quasi certi): se l'annotatore li avesse marcati "niente", il
    campione sarebbe stato dichiarato rumore. Qui i controlli sono *non*-confini, che non
    garantiscono nulla — quindi non c'è modo di distinguere "OSG sbaglia" da "l'annotazione è
    rumorosa". Candidati per il prossimo giro: i cartelli di località di *Rogue One*
    (JEDHA/EADU/SCARIF), che sono cambi di scena certi.
  - **Il 15% sui controlli non torna.** Implica ~480 cambi di scena su 3204 stacchi, cioè una
    scena ogni **16 s** su un film di 2h14 — non è la "scena" del manuale (unità di continuità
    temporale, r. 1591), è più vicino al cambio di luogo o di inquadratura. O l'annotatore usa
    una nozione più larga (dichiarato: non è un esperto di cinema), o k=126 è molto sotto il vero.
    Le due cose si separano solo esaurendo *tutti* gli stacchi di un tratto continuo del film
    (~15 min) invece di campionarli: dà insieme il tasso vero di scene e la calibrazione
    dell'annotatore.
- [ ] 🟡 **Diarizzazione + linking (Fase 2).** `speech diarize --engine sortformer` (0,90 s / 180 s,
  Neural Engine, niente token HF). Ordine: diarizzazione → linking speaker↔volto per co-occorrenza →
  nomi dai vocativi come `name_hint`+score (non sovrascrivere `Personaggio N`) → poi active speaker
  detection se serve. Dipende da: 4.4 (cluster volti stabili).
  - [ ] 🔵 **Sortformer ~4 speaker** (non verificato): limite su film corali, da controllare.
  - [ ] 🔵 **`speech embed-speaker`** — gallery vocale per personaggio, linking voce↔volto più solido
    che passare per i nomi.
  - [ ] 🔵 **Parlante che attraversa lo stacco** = indizio di *stessa scena* (campo/controcampo).
    Segnale gratis dalla diarizzazione, da misurare — utile alla Fase 1.
- [ ] 🟡 **Ricerca sul catalogo (3.4).** Caption + transcript + embedding per scena → `index.html`
  cercabile (faiss + SigLIP, entrambi MIT/adottabili). Rende molto di più **dopo** la Fase 1.

---

## 6 · Infrastruttura / debito

- [ ] 🔵 **Filtro per confidenza nella UI** — il 25% degli shot ha confidenza < 0,2 (soglia 0,05).
  Non è un bug (sono shot che prima non vedevamo) ma la UI li mostra come gli altri. **Una riga di JS.**
- [ ] 🔵 **Frame condivisi faces+vlm** — oggi campionano gli stessi shot in modo indipendente (6
  seek@640 + 3 seek@512). Condividerli vale ~2-3 min/film. È l'unica parte della 3.1 sopravvissuta.
- [ ] 🔵 **Setup plug-and-play — la coda.** Meccanismo fatto (`weights.py`, `scene-detector-setup`);
  ogni modello aggiunto (SigLIP, `speech`, Omni) allunga la coda da bonificare. I 3 modelli grandi
  (`--models`) non sono collaudati da zero su macchina pulita, nessuno ha hash verificato.

---

## Deciso — non si fa (per non riaprirlo)

| Cosa | Perché | Rif |
|---|---|---|
| ⛔ Decode-once multi-output ffmpeg (3.1) | premessa falsa, `hwaccel` è 0,24× sul path 48×27 | UPGRADE §3.1 |
| ⛔ VLM server + APC (3.3) | prefisso cacheable 2%, non ripaga | UPGRADE §3.3 |
| ⛔ WhisperX | il vantaggio è il chunking, non il modello; vuole torch 2.8 | UPGRADE §4.3 |
| ⛔ Opzione A (`min_scene_len` da solo) | +1 punto F1, non 6; le corse (B) dominano | SESSIONE-07-23 §5.7 |
| ⛔ Ancora b/n VLM | 0/35 con e senza, su Qwen3-VL | UPGRADE §0.2 |
| ⛔ Rimuovere dep `scenedetect` / vendored | baseline documentata / rischio `state_dict` | Audit #7, #17 |
