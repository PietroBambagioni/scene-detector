# Scene Detector — Piano di Upgrade

> Documento di indirizzo tecnico. Nasce da una revisione del progetto e da un run reale
> di collaudo su *Anna* (Grifi & Sarchielli, 1975), il cui `manifest.json` ha smentito metà
> delle ipotesi di partenza e ne ha confermata l'altra metà. Le priorità qui sotto seguono
> quelle prove, non l'intuito.

---

## Principio guida

Tre lezioni, in ordine di importanza.

**1. Il nome promette una cosa che la pipeline non fa.** Si chiama *Scene* Detector ma rileva
*shot*. Manca lo stadio che raggruppa gli shot in scene — cioè l'unica cosa che trasforma
un elenco di clip in un catalogo navigabile. Finché quello stadio non esiste, il nome è un
assegno scoperto.

**2. Il collaudo ha ribaltato le priorità.** Il difetto rumoroso — "le clip sono troppo
lunghe, 1-3 minuti" — non era un difetto: *Anna* è un film genuinamente lento, girato con una
delle prime videocamere open reel portatili in Italia, fatta apposta per riprese lunghissime.
I difetti veri erano silenziosi e stavano corrompendo il catalogo senza farsi notare: un terzo
dei dialoghi inventato, descrizioni a colori su un film in bianco e nero, personaggi assenti
dal manifest, una confidenza che è solo un flag travestito. **Un output plausibile non è un
output corretto.**

**3. Da qui discende l'ordine dei lavori:**

```
Fase 0  →  Fase 1  →  Fase 2  →  Fase 3  →  Fase 4
 bug        scene      chi dice    infra     modelli
 veri       (il nome)  cosa       (velocità) (misurare prima)
```

Prima si aggiusta ciò che è dimostrabilmente rotto. Poi si costruisce la feature che il nome
promette. Poi si rende veloce. **Solo alla fine** si cambiano i modelli — e mai per riparare un
bug che non è stato prima localizzato. *Anna* ha dimostrato che il detector era sano proprio
dove avrei scommesso il contrario: non si sostituisce un modello sulla base di un'impressione.

---

## Le prove (Anna, 1975)

Tutto ciò che segue è misurato sul `manifest.json` del run reale.

| Metrica | Valore | Lettura |
|---|---|---|
| Durata | 12 829 s (3h 33m) | — |
| Shot | 373 · ASL 34,4 s | anomalo? No: film osservativo |
| Durate shot | min **0,68 s** · mediana **18,2 s** · max 316,6 s | asimmetrica a destra = detector sano |
| Copertura | Σ durate = `duration` esatto | lo splitter non collassa nulla |
| Dialoghi solo "Grazie a tutti" | **78 / 238 (33%)** · 77 min di film | allucinazione ASR canonica |
| Descrizioni a colori (film in b/n) | 6 / 373, incluso lo **shot 0** | il VLM riempie i vuoti |
| Personaggi nel manifest | **0** | run *anteriore* al commit `117fd27` — vedi 0.3 |
| Valori di confidence | solo **1.0 / 0.5** (270 / 103) | flag binario, non confidenza |

Nessun pavimento a 60 secondi (il minimo è 0,68 s), nessun buco tra gli shot. Il detector ha
ragione; il catalogo mente altrove.

---

## Fase 0 — Il catalogo mente (bug in produzione)

Questi non sono miglioramenti: sono difetti che *oggi* producono output sbagliato. Vanno
prima di tutto il resto, perché ogni stadio a valle (scene, ricerca, diarizzazione) consuma
questi dati e ne eredita gli errori.

### 0.1 · ASR — un terzo dei dialoghi è inventato

Su 238 shot con dialogo, **78 contengono soltanto "Grazie" / "Grazie a tutti"**, spesso in
loop (`40× "Grazie a tutti"`, `13× "Grazie a tutti Grazie a tutti"`, …). È l'allucinazione
italiana canonica di Whisper sul non-parlato — la sorella di "Sottotitoli a cura di…". Si
concentra sulle riprese lunghe (durata mediana degli shot colpiti: 41,5 s contro i 18 s del
film), cioè dove la macchina resta accesa e non parla nessuno: **77 minuti** di film con
dialogo fabbricato.

Era prevedibile: il restauro del 2011 ha *volutamente conservato* i difetti del magnetico 16mm
(fruscio, interferenze, ronzio di microfono). È esattamente il substrato su cui Whisper
allucina, e il VAD attuale non lo regge.

**Cosa fare** (dal più economico):
- Filtro a valle, ~10 righe: uno shot il cui *unico* contenuto è una frase della blacklist, o
  che ripete lo stesso n-gramma, non è dialogo → si scarta. Ripulisce il manifest subito.
- `condition_on_previous_text=False` — è ciò che alimenta il loop di ripetizione.
- VAD più aggressivo (`min_silence_duration_ms` più corto, soglia più alta).
- `no_speech_threshold` + `compression_ratio_threshold` per scartare i segmenti degeneri.

> **Stato: implementato e validato su *Anna*.** In `transcription/asr.py`:
> `condition_on_previous_text=False` + funzione pura `is_hallucination` (blacklist "grazie…",
> prefisso "sottotitoli…", loop di n-gramma ripetuto ≥3×) che scarta i segmenti a monte, con
> test in `tests/test_asr.py`. I due knob restanti (VAD più aggressivo,
> `no_speech_threshold`/`compression_ratio_threshold`) lasciati ai default: da toccare **solo
> se** emergono allucinazioni residue — su audio degradato alzare le soglie rischia di tagliare
> dialogo vero.
>
> **La diagnosi qui sopra era incompleta.** Ri-trascrivendo il cluster shot 38–48 (dove
> l'originale segnava `"Grazie a tutti"`) col codice nuovo, **tutti e 7 gli shot contengono
> dialogo reale** (un monologo su carcere e politica). Il problema non era "Whisper riempie il
> silenzio": era un **runaway loop di `condition_on_previous_text`** che, sull'intero film
> trascritto in un'unica chiamata, si auto-alimenta e **sovrascrive il parlato reale** per
> decine di shot. Non 77 minuti di *vuoto riempito* ma, in buona parte, **dialogo vero
> distrutto**. Ciò spiega perché il loop **non** si riproduce trascrivendo una fetta isolata
> (niente contesto accumulato) e perché `condition_on_previous_text=False` — che non trasporta
> contesto — lo previene alla radice: sui 7 shot recupera il dialogo che il catalogo aveva
> perso, tenendo il silenzio vero (shot 39) e il "Grazie mille" legittimo (shot 38).
>
> **Ri-collaudo sull'intero film** (12 thread, 41 min, `manifest.cleaned.json`): shot
> interamente allucinati **76 → 1** (l'unico residuo, shot 74 `"Com'era? Com'era? Com'era?"`, è
> plausibilmente parlato vero, non un artefatto); shot con dialogo **238 → 266**; parole di
> dialogo totali **11 170 → 21 640 (+10 470)**. Dei 76 shot allucinati, 70 ora contengono
> dialogo reale e 6 sono correttamente vuoti. Il loop stava **sopprimendo circa metà del
> parlato del film**.

### 0.2 · VLM — vede a colori un film in bianco e nero

*Anna* è video trasferito su 16mm, bianco e nero. Ventidue descrizioni lo riconoscono ("scala
di grigi"); sei no — e una è lo **shot 0**, la prima cosa che si legge aprendo `index.html`:
*"una figura femminile con capelli rossi… un ambiente urbano con elementi di design moderno"*,
in un Portapak del '72. Sei su 373 è poco in percentuale, ma è la vetrina del catalogo ed è la
prova che **Qwen2.5-VL-3B a 4 bit sta riempiendo i vuoti** invece di descrivere.

**Cosa fare:** ancoraggio nel prompt ("il film è in bianco e nero, non menzionare colori") come
tampone immediato; la soluzione vera è il cambio modello in Fase 4.2.

> **Stato: implementato.** In `captioning/caption.py`: `_is_grayscale(frames)` misura la chroma
> media (max−min tra canali) dei frame *già campionati* per lo shot; se sotto soglia,
> `build_prompt(..., grayscale=True)` aggiunge l'ancora "l'inquadratura è in bianco e nero: non
> menzionare colori". **Rilevato per-shot, non hardcodato**: la pipeline è generale — inchiodare
> "il film è in b/n" romperebbe i film a colori, e il per-shot ancora correttamente anche un
> flashback in b/n dentro un film a colori. Test in `tests/test_caption.py`
> (`_is_grayscale` b/n vs colore, `build_prompt` con/senza ancora).

### 0.3 · I personaggi non arrivano nel manifest — ~~aperto~~ **risolto (`117fd27`)**

La diagnosi originale ("niente volti, niente cluster, niente nomi") era vera sul manifest di
*Anna*, ma quel run è **anteriore** al commit `feat: riconoscimento personaggi (InsightFace)`.
Oggi lo step esiste ed è cablato end-to-end:

- `catalog/manifest.py` — lo schema ha `cast: []` a livello film e `characters: []` per shot.
- `pipeline.py` — lo step `faces` (gated da `--faces`) chiama `recognize_characters`, popola il
  cast e i personaggi per shot, con resume dal manifest su disco.
- `captioning/caption.py` — legge `cast`/`characters` e nomina i personaggi nel prompt VLM.
- `recognition/` — SCRFD+ArcFace, clustering coseno, matching gallery; test in `tests/test_recognition.py`.

Restano **due riserve**, nessuna bloccante:
1. ~~**Da validare su run.**~~ ✅ **Validato su *Anna*** (6,9 min, 373 shot × 6 frame, CoreML):
   **1634 volti → 68 cluster**, personaggi in **243/373 shot**. Lo step funziona end-to-end; il
   run originale semplicemente non passava `--faces`.
2. **Qualità grezza — confermata dal run.** `recognition/identify.py` clusterizza i *singoli
   volti*, non i tracklet, e su *Anna* si vede: **68 cluster** per un film con una decina di
   presenze reali. Le thumbnail dei primi cluster mostrano la protagonista correttamente isolata
   (73 shot) ma anche volti che si ripetono in cluster distinti — la stessa persona spezzata in
   più identità. **Questo rende la 4.4 un prerequisito della Fase 2**, non un raffinamento
   opzionale: qualunque legame nome↔personaggio costruito su cluster frammentati eredita la
   frammentazione.

### 0.4 · La confidence è un flag travestito

Due soli valori: `1.0` (270 shot) e `0.5` (103). Non è una confidenza, è un booleano
"i due detector hanno concordato / no" — e dice che TransNet e AutoShot **litigano sul 28%
degli stacchi**. La probabilità per-frame di TransNetV2 è già calcolata internamente e
darebbe uno score continuo e calibrato al posto di questo binario. Vedi Fase 4.1 per il
ripensamento completo dell'ensemble.

> **Stato: implementato.** La confidenza di ogni shot è ora la **prob per-frame di TransNetV2
> al taglio che lo apre** (`probs[start−1]`; primo shot = 1.0, inizio film), non più 1.0/0.5.
> `boundary_confidences` in `detection/neural.py` la calcola per il detector singolo;
> `reconcile` in `detection/confidence.py` la usa per l'ensemble — con un effetto che il binario
> nascondeva: un boundary visto **solo da AutoShot** prende la prob (bassa) di TransNet a quel
> frame, cioè "il detector primario non l'ha visto", invece di un opaco 0.5. **L'accordo tra i
> due detector resta come segnale separato** in `flags` (la lista dei boundary da rivedere,
> già loggata). Test in `tests/test_confidence.py` + `tests/test_scene.py`
> (`boundary_confidences`, `scenes_from_ranges(confidences=…)`).

---

## Fase 1 — Da shot a scena (la ragione del nome)

Lo stadio mancante. Prende la lista di shot che hai già e decide **quali stacchi sono anche
cambi di scena**, collassando ~2000 shot in ~150 scene. È ciò che rende il catalogo davvero
navigabile e che riduce il captioning VLM di un ordine di grandezza (150 chiamate per scena
invece di 2000 per shot).

| Opzione | Costo | Prestazioni (MovieNet) | Verdetto |
|---|---|---|---|
| **DIY** — embedding SigLIP per shot + clustering con vincolo temporale | ore | decente | punto di partenza |
| **TranS4mer** — 37M param, 1 GB, 0.24 s/shot | basso | 48.4 F1 / 60.8 AP | **scelta pragmatica per Mac** |
| **Scene-VLM** — Qwen2.5-VL-7B LoRA (Amazon Prime Video, dic 2025) | alto | 62.1 F1 / 66.8 AP (SOTA) | riferimento, non commit |

~~**Raccomandazione: TranS4mer.**~~ **Corretto dopo verifica dei repo (lug 2026): TranS4mer è
nella stessa condizione di Scene-VLM.** Il repo ufficiale
([md-mohaiminul/TranS4mer](https://github.com/md-mohaiminul/TranS4mer), 34 ⭐, Apache-2.0, fermo a
giu 2023) ha la sezione *Pre-trained Models* con scritto **"TODO"**: nessun checkpoint. Il flusso
documentato è pre-training BaSSL → finetune, su CUDA 11.3. "Adottarlo" significa **addestrarlo** —
esattamente ciò per cui il piano scartava Scene-VLM. La riga "gira sul Mac senza accorgersene"
valeva per il modello, non per la sua disponibilità.

**Le due strade realmente percorribili:**

- **[BaSSL](https://github.com/kakaobrain/bassl)** (Kakao Brain, 142 ⭐, **Apache-2.0**) — *ha* un
  Model Zoo con checkpoint (56,26 / 57,40 AP su MovieNet). È il pre-training su cui TranS4mer si
  appoggia. Restano da verificare due cose: se i pesi pubblicati siano quelli *finetuned* per lo
  scene boundary o solo i self-supervised, e quanto costi il path di inferenza su un film nuovo
  (il repo documenta pretrain/finetune, non un `predict` su file).
- **[SceneSeg / LGSS](https://github.com/AnyiRao/SceneSeg)** (CVPR 2020, 237 ⭐) — ha modelli
  pre-addestrati e un tool di segmentazione temporale pensato come "easy-to-use". Più vecchio e
  meno accurato, ma è l'unico con un percorso di inferenza dichiarato. **Attenzione: nessuna
  licenza dichiarata** — da chiarire prima di dipenderci.

Scene-VLM resta il tetto teorico e resta senza codice né pesi. Il DIY (embedding SigLIP per shot +
clustering con vincolo temporale) sale di conseguenza: non è più il ripiego, è il piano B serio.

**Due trappole da conoscere prima di scrivere codice:**

- **Lo zero-shot non funziona.** Chiedere a un VLM di raggruppare senza fine-tuning: Qwen2.5-VL-7B
  fa **11.1 F1**, Claude Sonnet 4.5 fa **37.6**, contro i 62.1 del modello addestrato. Serve un
  encoder dedicato (TranS4mer) o il fine-tuning. Non c'è scorciatoia via prompt.
- **La scena si riconosce guardandola.** Dall'ablation di Scene-VLM: solo visivo → 58.6 F1; con
  sottotitoli + identità personaggi → 62.1. Cioè dialoghi e personaggi — le due cose che ti
  verrebbe voglia di cablare per prime perché ce le hai già — valgono **~3,5 punti in tutto**
  (sottotitoli da soli: 31.5; attori da soli: 24.8). Questo conferma TranS4mer solo-visivo come
  scelta giusta e ridimensiona l'ansia di collegare subito ASR e volti al grouping.

**Dipendenza:** questo stadio consuma i dialoghi. Va **dopo** la Fase 0.1, o erediti il 33% di
allucinazioni dentro le feature di raggruppamento.

---

## Fase 2 — Chi dice cosa (la feature che collega ciò che hai)

Hai i volti (quando la 0.3 sarà risolta) e hai i dialoghi. Non li colleghi. La **diarizzazione**
lo fa: divide l'audio per parlante, e poi si lega ogni cluster-parlante a un cluster-volto per
co-occorrenza — statistica banale sopra dati che già calcoli, ma cambia il manifest da "c'è del
dialogo" a "**Anna** dice: …".

- **Diarizzazione:** `pyannote/speaker-diarization-community-1` (modello di produzione attuale)
  oppure **NeMo Sortformer** (end-to-end unificato).
- **Chi parla nell'inquadratura:** active speaker detection (TalkNet / Light-ASD) per legare la
  voce al volto visibile, non solo al parlante audio.
- **Allineamento fine:** `word_timestamps=True` nell'ASR. Evita che una battuta a cavallo di uno
  stacco finisca nella clip sbagliata — problema concreto su un film con ASL 18 s dove i confini
  contano.

Priorità media: è una feature nuova di valore alto, ma poggia su 0.3 (volti nel manifest) e
0.1 (dialoghi puliti). Non ha senso prima.

---

## Fase 3 — Infrastruttura (velocità e pulizia)

Nessuna di queste cambia i risultati; cambiano tempo di parete, spazio su disco e qualità dei
bordi. Vanno prima della Fase 4, perché aggiungere modelli sopra un'infrastruttura che decodifica
il film quattro volte moltiplica lo spreco.

### 3.1 · Decodificare una volta sola

TransNet vuole 48×27, AutoShot idem, i volti full-res, il VLM 3 frame/shot. Se ogni stadio
ri-decodifica, stai decodificando il film **quattro volte**. Un singolo passaggio ffmpeg
multi-output con `-hwaccel videotoolbox` sposta i tempi più di qualsiasi cambio di modello.

> **Stato: verificato su *Anna* (Mac/MPS) — premessa falsa, NON adottato.** La misura smentisce
> due cose:
>
> - **Non ci sono 4 decode del film.** La detection è **già decode-once** (48×27 condiviso tra
>   TransNet e AutoShot in ensemble, fix in `PLAN_FIXES`). Faces e VLM **non** decodificano il
>   film: fanno estrazione *sparsa* a seek (`ffmpeg -ss -frames:v 1`, 6 e 3 frame/shot); l'ASR
>   decodifica l'**audio**. Un unico passaggio multi-output che decodifica *tutti* i frame a
>   piena risoluzione sarebbe **più lento** per i consumatori sparsi (a loro servono 3-6 frame per
>   shot, non 320 000).
> - **`-hwaccel videotoolbox` è una regressione 4× sul path detection.** Decode 48×27 di 60s di
>   Anna: **1278 frame/s** software vs **309 frame/s** con videotoolbox (**0.24×**) — il readback
>   GPU→CPU per frame supera il decode banale a 48×27. Film intero ~251 s (4 min), comunque
>   marginale contro ASR (41 min) e VLM (~12 min).
>
> **Nucleo di verità rimasto (non fatto):** quando `--faces` e `--vlm` girano insieme campionano
> gli **stessi shot** in modo indipendente (6 seek@640 + 3 seek@512). Condividere i frame
> (campiona una volta, riusa a valle) vale ~2-3 min — piccolo, opportunistico, non l'ffmpeg
> multi-output del piano.

### 3.2 · Non tagliare le clip di default

373 (o 2000) file duplicano il film su disco, e con `-c copy` i tagli si allineano ai keyframe:
su uno shot di 3 secondi l'errore è enorme in proporzione. Il manifest ha già i timecode →
`index.html` può usare **media fragments** (`#t=start,end`) su un file solo. Il taglio diventa
export on-demand e il dilemma copy/reencode sparisce. Se devi tagliare davvero: *smart cut*
(reencode solo dei GOP ai bordi).

### 3.3 · VLM come server con prefix cache

Oggi rifai il prefill dello stesso system prompt ~2000 volte per film. **mlx-vlm ha ora prefix
caching automatico (APC) e una modalità server:** server persistente + APC = il prompt di
sistema lo paghi una volta sola. È un guadagno maggiore del cambio modello stesso.

> **Stato: verificato su *Anna* (Mac/MPS) — capability presente ma NON ripaga, non adottato.**
> Server e APC **esistono** in mlx-vlm 0.6.5 (`mlx_vlm/apc.py`, `mlx_vlm/server/`). Ma l'APC è
> prefix-cache a blocchi la cui chiave **include il contenuto dell'immagine** (`extra_hash`),
> quindi tra shot con immagini diverse riusa solo i blocchi *prima* della prima immagine. Misura
> su uno shot reale:
>
> - prefill = **741 token**: **540 immagine (73%)** + 201 testo; il prefisso condivisibile prima
>   della 1ª immagine è **15 token (2%)** (Qwen mette le immagini *prima* dell'istruzione).
> - `generate` per shot ≈ **2,05 s**, dominato dal **decode dell'output** (~100 token) che l'APC
>   **non tocca**; il prefill è una minoranza.
> - il modello lo teniamo **già residente** (`load` una volta in `__init__`, riusato per ogni
>   shot): il server non aggiunge nulla, solo IPC.
>
> Best case ~2-5% per shot (27% *del solo prefill* ristrutturando l'istruzione come system).
> **Il vero moltiplicatore sul VLM è fare meno chiamate → Fase 1** (scene grouping), non l'APC.

### 3.4 · Catalogo interrogabile

Caption + transcript (pulito) + un embedding per scena rendono `index.html` cercabile. È la
differenza tra un catalogo e una cartella di clip — e con il grouping della Fase 1 diventa
"cerca la scena in cui…".

---

## Fase 4 — Swap di modelli (opzionali, misurare prima)

Solo dopo che il catalogo è corretto (Fase 0) e l'infrastruttura è sana (Fase 3). Ogni riga qui
è un miglioramento potenziale, non un obbligo: **misurare sul proprio hardware prima di
adottare.**

### 4.1 · Shot detection — OmniShotCut e il ripensamento dell'ensemble

TransNetV2 regge ancora: nei paper 2026 è la baseline da battere. Ma è uscito **OmniShotCut**
(UVA CV Lab, apr 2026, pip-installabile): F1 0.881 contro 0.75-0.82, e soprattutto **transition
IoU 0.644 contro 0.18-0.25** — cioè delimita le dissolvenze, non solo le trova. Riconosce anche
il *tipo* di transizione (dissolve, fade, wipe), metadati che starebbero bene nel manifest.
*Caveat:* il README chiede PyTorch con CUDA → **su MPS va verificato prima di impegnarcisi.**

L'**ensemble va ripensato a prescindere.** AutoShot nasce per lo short-form e condivide con
TransNetV2 gli stessi thumbnail 48×27 e uno spazio NAS derivato da TransNetV2 → errori
correlati. "Accordo = confidenza" dice poco perché **sbagliano insieme** (lo conferma il 28% di
disaccordo puramente binario del manifest). Meglio: usare la probabilità per-frame di TransNetV2
come confidenza continua; se serve una seconda opinione vera, prenderla architetturalmente
diversa (non un cugino di TransNet).

> **Stato: verificato su *Anna* (Mac/MPS) — il caveat CUDA è falso, gira. Fattibile, non
> ancora adottato.** Il modello è stato scaricato, patchato e fatto girare davvero.
>
> - **MPS funziona.** Il "richiede CUDA" del README è superficiale: **3 righe** `.to("cuda")`
>   hardcoded in `omnishotcut/engine.py`, nessun kernel custom (niente deformable attention).
>   L'architettura è DETR standard — **ResNet18 + 6 layer encoder/decoder, 41 M param**, input
>   **128×96**, finestra 100 frame, 24 query. Sostituite quelle 3 righe con un device
>   parametrico, gira su MPS senza fallback CPU. Checkpoint 164 MB, **MIT anche i pesi**.
> - **Costo (Anna, 5 min di film reale):** decode **930 fps**, inference **522 fps** su MPS
>   → film intero ≈ **16 min** (5,7 decode + 10,2 inference) contro i ~4 min del path attuale.
>   Peak RSS 1,52 GB. Su CPU l'inference è ~3× più lenta.
> - **Accuratezza sugli stacchi netti: pari, non superiore.** Su 5 boundary di *Anna* confrontati
>   col manifest: **3 esatti al frame** (delta 0), 1 a **2 frame**. Nessuna sovra-segmentazione.
> - **Dove si vede la differenza:** nell'unico punto ambiguo del campione (frame 2270-2294 del
>   segmento 1200-1500 s: un movimento rapido di camera, non un taglio) OmniShotCut restituisce un
>   **range di transizione etichettato** (`Wipes` / `Transition_Source`), mentre il manifest piazza
>   un punto secco 69 frame più avanti con confidenza 0,5. È esattamente il transition IoU: i tipi
>   disponibili sono Dissolve/Wipes/Push/Slide/Zoom/Fade/Doorway (intra) e New_Start/Hard_Cut/
>   Transition_Source/Transition/Sudden_Jump (inter).
> - **Numeri del paper (corretti):** su *OmniShotCutBench* — Range F1 **0,883** contro 0,814 di
>   TransNetV2 e AutoShot (**+7 punti**), transition IoU **0,632** contro **0,192** di TransNetV2
>   (**3,3×**). Il guadagno vero è tutto sulle transizioni graduali; sui cut netti il margine è
>   modesto. *Caveat:* il benchmark **non è rilasciato** ed è costruito con la loro pipeline di
>   transizioni sintetiche — i numeri non sono riproducibili in locale.
> - **Due ostacoli di integrazione, entrambi risolvibili:** (a) `inference(path)` decodifica
>   l'**intero** video in RAM — **11,8 GB** per Anna a 128×96: va chunkato passando array numpy
>   (l'API li accetta) gestendo l'offset a mano, ~40 righe; (b) serve **torchvision** (14 MB, oggi
>   assente) e un fork/vendor per il `.to("cuda")`, su un repo di ricerca senza training code.
>
> **Verdetto: rimandare, non scartare.** Su *Anna* non ripagherebbe — stacchi netti, dove il
> vantaggio è di 7 punti F1 al prezzo di 4× il tempo di detection e una dipendenza da un repo di
> ricerca. Diventa interessante su materiale **con dissolvenze e fade**, dove il transition IoU
> 3,3× e le etichette di transizione entrano nel manifest come metadati nuovi. Da riprendere
> insieme al collaudo su cinema a montaggio serrato già previsto per la Fase 1.

### 4.2 · VLM — Qwen3-VL

Qwen2.5-VL-3B-4bit è due generazioni indietro (ed è la causa delle descrizioni a colori della
0.2). **Qwen3-VL** — dense 2B/4B/8B/32B + MoE 30B-A3B, contesto interleaved fino a 256K,
percezione spaziale e comprensione delle dinamiche video migliorate (il caso d'uso esatto) —
è supportato nativamente da mlx-vlm. **Passare a 4B in 8-bit o 8B in 4-bit:** a 3B in 4-bit si
paga la quantizzazione due volte. Si combina con il server + APC della 3.3.

> **Stato: A/B misurato su *Anna* → adottato `Qwen3-VL-4B-Instruct-8bit` come default.**
> Confermato prima che mlx-vlm 0.6.5 supporta `qwen3_vl` (il pin `<0.7` non blocca). A/B sugli
> shot che il modello attuale aveva allucinato a colori (dal `manifest.json` reale), **senza
> l'ancora b/n** di 0.2, per isolare il comportamento *nativo*:
>
> - **Colori risolti 4/5.** Shot 14 ("capelli rossi") → "immagine nera con logo Rai"; shot 61
>   ("nastro rosso") → "due uomini… **in bianco e nero**"; shot 53/87 ("capelli biondi") → puliti.
>   Il candidato **dichiara spontaneamente "in bianco e nero"** in 5/7 descrizioni senza ancora —
>   esattamente la radice che 0.2 prevedeva. Residuo: shot 0 (cartello di apertura) migliora la
>   content-accuracy (legge il testo vero) ma miscolora il grafico → **l'ancora 0.2 resta** come
>   rete per questi casi (cintura + bretelle).
> - **Qualità generale migliore** (meno fabbricazioni tipo "donna con lunghi baffi").
> - **Costo:** s/shot **2,11 → 2,94 (+39%)**, RAM di picco **3,48 → 5,38 GB (+55%)**. Accettabile
>   (il VLM è uno step isolato, non gira in parallelo alle reti).
>
> Cablato in `core/config.py`, `cli.py`, `captioning/caption.py` (+ README/OVERVIEW); percorso di
> produzione `MlxVlmCaptioner` verificato end-to-end su Anna, 63/63 test verdi. **3.3 (server+APC)
> resta scartato** — non si combina con nulla.
>
> **A/B fra taglie (4B-8bit · 8B-4bit · 8B-8bit) su *Anna* → adottato `8B-4bit` come default.**
> **36 shot stratificati** su tutto il film (shot 0→358; sei celle da sei: corto/medio/lungo ×
> con dialogo/muto, seed fisso), frame estratti **una volta** con `sample_frames` di produzione e
> riusati identici dai tre modelli, greedy (`temperature=0`) per attribuire le differenze al
> modello e non al sampling, un processo per modello. Un primo giro su 8 shot aveva dato
> indicazioni che il campione ampio ha in parte **smentito** — vedi sotto.
>
> | | s/shot | peak RAM | 373 shot | colori su b/n | deriva dial. | meta-rif. | troncate |
> |---|---|---|---|---|---|---|---|
> | 4B-8bit | **4,42 s** | **6,21 GB** | 27,5 min | 0/35 | 6,2% | **7/36** | **3/36** |
> | **8B-4bit** | 5,50 s (+24%) | 6,75 GB (+9%) | 34,2 min | 0/35 | **1,4%** | **0/36** | **0/36** |
> | 8B-8bit | 8,83 s (+100%) | 10,85 GB (+75%) | 54,9 min | 0/35 | 2,9% | 2/36 | 0/36 |
>
> **Il problema dei colori è chiuso per tutta la famiglia:** *zero* menzioni di colore su 35 shot
> b/n, in tutte e tre le taglie. Non serviva un modello più grande per risolvere la 0.2 — bastava
> uscire da Qwen2.5.
>
> **Quello che separa 4B e 8B è la fabbricazione, e si vede sui fotogrammi.** Shot 3 è un
> **cartello di testo** sul restauro digitale: il 4B descrive *"un uomo in piedi, vestito con un
> abito formale, la testa leggermente inclinata, luce frontale che crea ombre nette sul volto"* —
> sessanta parole inventate su un'inquadratura che non contiene persone; entrambi gli 8B leggono
> il testo e lo riassumono. Shot 191: il 4B vede *"una donna che parla al telefono"* (nessun
> telefono nell'inquadratura), gli 8B leggono il riflesso nell'acqua increspata e la mano vicino
> alla bocca. Le metriche dicono la stessa cosa in aggregato: il 4B apre con "le tre immagini
> mostrano…" nel **19% dei casi** (l'8B-4bit mai) ed è l'unico che si fa **troncare** da
> `max_tokens=128`, perché è anche il più verboso (56 parole contro 47 e 43).
>
> **Due conclusioni del giro piccolo, corrette dal campione ampio:** il nome "Emma" **non era
> un'allucinazione** — è nel dialogo ASR ("Tu che dici, Emma?") e tutti e tre lo usano
> correttamente. E la **deriva narrativa non cresce con la taglia**: sui 36 shot il massimo è del
> **4B (6,2%)** e il minimo dell'8B-4bit (1,4%). L'inferenza opposta, tratta da 8 shot, era
> sbagliata.
>
> **Verdetto: `8B-4bit`.** Domina il 4B su ogni metrica di qualità al prezzo di **+24% di tempo e
> +9% di RAM** — sul film sono 7 minuti. L'`8B-8bit` costa **il doppio** del 4B in tempo e +75% di
> RAM per un margine sottile sull'8B-4bit (qualche dettaglio in più: l'ombrello dello shot 191, la
> sigaretta dello shot 47): tenerlo come opzione via `--vlm-model` se il catalogo punta sulla
> descrizione fine, non come default. Con lo scene grouping (Fase 1) tutte le proiezioni si
> dimezzano. Cablato in `core/config.py`, `cli.py`, `captioning/caption.py` + README/OVERVIEW;
> 63/63 test verdi.

### 4.3 · ASR — restare o Parakeet

`large-v3-turbo` va bene, soprattutto per l'italiano. **Parakeet v3** fa 6.32% WER contro 7.44%,
ma copre 25 lingue europee contro le 99 di Whisper e il margine è su parlato *pulito* — non su
audio cinematografico degradato come quello di *Anna*. Il vero problema dell'ASR non è il modello
ma le allucinazioni (Fase 0.1). Su memoria unificata conviene comunque **non** far girare ASR e
reti neurali in parallelo: lo split attuale (ASR su CPU, reti su MPS) potrebbe già essere la
scelta giusta. Misurare, non intuire.

> **Stato: WhisperX e speech-swift provati su *Anna* (lug 2026).** Segmento 1530-1710 s (shot
> 47+48, 180 s, intervista a più voci), confronto diretto col dialogo del manifest attuale.
>
> - **[WhisperX](https://github.com/m-bain/whisperX) 3.8.6 — meglio del nostro ASR su tre fronti.**
>   **487 parole contro 445 (+9,4%)**; **zero** 4-grammi ripetuti ≥3× contro i tre del manifest
>   attuale (`"non ti puoi parlare"` ×3 — residuo dello stesso loop della 0.1); **487/487 parole
>   con timestamp e score**. Il motivo è architetturale: WhisperX segmenta con VAD *prima* di
>   trascrivere (Cut & Merge + batched inference), quindi il runaway di
>   `condition_on_previous_text` non può innescarsi. **Costo:** 49,9 s per 180 s = **3,6× realtime**
>   su CPU contro i 5,2× del nostro setup → film intero ≈ **59 min contro 41**.
>   *Va isolato:* porta `torch 2.8` e `transformers 4.57`, incompatibili col venv del progetto
>   (2.13 / 5.14.1). La sua diarizzazione usa pyannote **gated** (serve token HF) — ma
>   l'allineamento gira benissimo da solo.
> - **[speech-swift](https://github.com/soniqo/speech-swift) — nessun conflitto possibile.** È
>   Swift, si installa con `brew install speech`: binario separato, non tocca il venv.
>   **`speech diarize --engine sortformer`: 0,90 s per 180 s di audio (~200× realtime) sul Neural
>   Engine**, 3 parlanti con sovrapposizioni, **senza token HF**. Ha anche `align` (forced
>   alignment MLX/CoreML), `transcribe` (Qwen3-ASR/Parakeet/Whisper) e **`denoise`/`restore`** —
>   quest'ultimo interessante proprio per *Anna*, il cui restauro ha conservato fruscio e ronzio.
>
> **Verdetto dopo due prove decisive: WhisperX non serve — il suo vantaggio è il *chunking*, non
> il modello.**
>
> **Prova 1 — chunking VAD col nostro faster-whisper** (stesso modello, stesso venv, nessuna
> dipendenza nuova): VAD → finestre indipendenti ≤30 s → `transcribe` per finestra.
>
> | | parole | tempo (180 s) | loop |
> |---|---|---|---|
> | baseline (file intero, come `asr.py` oggi) | 455 | 31,1 s | 0 |
> | **chunked (finestre VAD)** | **488** | 36,7 s | 0 |
> | WhisperX | 487 | 49,9 s | 0 |
>
> Il chunking **recupera per intero** il divario (488 contro 487) a **+18%** di tempo invece del
> +45%, ed è **26% più veloce di WhisperX**. Il guadagno viene dal decodificare finestre brevi e
> indipendenti, non dal codice di WhisperX: ogni finestra riparte da zero e Whisper non ha spazio
> per avvitarsi. *Nota:* su 180 s isolati nemmeno la baseline produce loop — il
> `"non ti puoi parlare"` ×3 del manifest nasce sulla lunga distanza, quindi la conferma finale
> richiede un run sull'intero film.
>
> **Prova 2 — `speech align`** (forced alignment nativo MLX): **487/487 parole in 3,38 s**, scarto
> **mediano 0,24 s** rispetto a WhisperX preso come secondo parere (non è ground truth). Sul caso
> reale del taglio a 87,2 s i due allineatori concordano su quale parola sta da che parte.
> **Riserve:** il **21% delle parole ha durata nulla** (start = end) e 5 parole finiscono *oltre*
> la durata dell'audio (fino a 204 s su 180). Basta per assegnare le parole agli shot — che è il
> nostro uso — non per una durata affidabile della singola parola.
>
> **Conclusione operativa:** ASR = faster-whisper **+ chunking VAD** (modifica interna, ~20 righe);
> word timestamps e diarizzazione = `speech` via subprocess. **WhisperX si chiude qui**: un venv
> parallelo da 1,3 GB con `torch`/`transformers` incompatibili, per un vantaggio che sappiamo
> riprodurre in casa.
>
> **Effetto collaterale utile per la Fase 1:** incrociando diarizzazione e confini shot, lo
> Speaker 2 parla da 83,8 s a 111,8 s **attraversando il taglio a 87,2 s**. Un parlante che
> continua attraverso uno stacco è un indizio di *stessa scena* (campo/controcampo). È un segnale
> diverso dai "sottotitoli" dell'ablation Scene-VLM — non richiede di capire *cosa* si dice — e
> arriva gratis dalla diarizzazione. Da misurare.

### 4.4 · Volti — clustering per traccia + licenza

Due cose:

- **Licenza (da correggere nei crediti).** InsightFace è MIT nel *codice*, ma i model package
  (`buffalo_l`, `antelopev2`, …) richiedono **licenza commerciale separata**. Nei crediti attuali
  "InsightFace — SCRFD + ArcFace (`buffalo_l`)" sta accanto a "TransNetV2 (MIT)" e si legge come
  se fosse la stessa cosa. Distinguerlo.
- **Clusterizzare le tracce, non i frame.** Mediare gli embedding sul tracklet dentro lo shot:
  da decine di migliaia di detection a poche centinaia di tracce, più robuste. Aggiungere il
  vincolo *must-not-link* (due volti nello stesso frame ≠ stessa persona) e pre-filtrare prima
  di embeddare (score, dimensione ≥ 50 px, blur, yaw). Nel cinema gran parte delle detection
  avvelena i cluster.

---

## Valutazione — misurare la cosa giusta

`eval.py` oggi riporta F1 sui boundary, che **nasconde per costruzione** il difetto che conta:
si può avere F1 0.82 e transition IoU 0.20 nello stesso modello — i confini sono solo
grossolanamente allineati alle transizioni reali. Sulle dissolvenze il point-matching dà ragione
anche quando sbagli di 15 frame.

- Dichiarare esplicitamente la **tolleranza** dei match.
- Aggiungere una **metrica range-based** (IoU sulle transizioni), o il failure mode resta
  invisibile: misureresti l'unica cosa che non può fallire.
- **Collaudare su un film che stacca ogni 5 secondi.** *Anna* è un banco di prova splendido per
  l'ASR (l'ha rotto nel modo più istruttivo) ma **pessimo per lo scene grouping**: pochi stacchi,
  tutti netti, tra riprese lunghe e stabili. Il giorno che colleghi la Fase 1, testala su cinema
  a montaggio serrato, o non saprai se funziona.

---

## Sintesi delle priorità

| # | Intervento | Impatto | Sforzo | Rischio | Blocca |
|---|---|---|---|---|---|
| ~~0.1~~ | ✅ Filtro allucinazioni ASR — *fatto, da validare su run* | alto | basso | nullo | 1, 2 |
| ~~0.3~~ | ✅ Personaggi → manifest — *fatto (`117fd27`), da validare* | alto | — | basso | 2 |
| ~~0.2~~ | ✅ VLM ancoraggio b/n — *fatto (auto-rilevato per-shot)* | medio | basso | nullo | — |
| ~~0.4~~ | ✅ Confidence continua — *fatto (prob per-frame TransNet)* | medio | basso | nullo | — |
| ~~3.1~~ | ⛔ Decodifica una volta — *verificato: premessa falsa, hwaccel 0.24×, non adottato* | — | — | — | — |
| **3.2** | Media fragments / no cut | medio | medio | basso | — |
| ~~3.3~~ | ⛔ VLM server + APC — *verificato: prefisso cacheable 2%, non ripaga* | — | — | — | — |
| **1** | Scene grouping (TranS4mer) | **massimo** | medio | medio | — |
| **2** | Diarizzazione + linking | alto | medio | basso | — |
| **3.4** | Ricerca sul catalogo | medio | medio | basso | — |
| **4.1** | OmniShotCut — *MPS verificato: gira; rimandato a un film con dissolvenze* | medio | medio | basso | — |
| ~~4.2~~ | ✅ Qwen3-VL — *A/B su 36 shot: adottato `8B-4bit` come default* | medio | basso | basso | — |
| **4.4** | Clustering per traccia + licenza | medio | medio | basso | — |

**Percorso minimo consigliato:** ~~0.1~~ → ~~0.3~~ → ~~3.1 + 3.3~~ → **1** → 2. Fase 0 è ora
**chiusa** (0.1/0.3 da validare con un ri-collaudo su *Anna*; 0.2/0.4 fatti). **3.1 e 3.3 sono
stati verificati e scartati** (le misure smentiscono le premesse su Mac/MPS — vedi i rispettivi
blocchi di stato): il prossimo passo azionabile è direttamente lo **scene grouping (Fase 1)**,
l'unico vero moltiplicatore sul costo VLM. Il resto è opportunistico.

---

## Crediti modelli (con licenza corretta)

- **TransNetV2** — Souček & Lokoč · codice e pesi MIT
- **AutoShot** — Zhu et al., CVPR-W 2023
- **PySceneDetect** — Castellano · BSD-3
- **InsightFace** — SCRFD + ArcFace · *codice MIT, model package `buffalo_l` sotto licenza
  commerciale separata*
- **faster-whisper** — Whisper / CTranslate2
- **Qwen2.5-VL** / **Qwen3-VL** — via mlx-vlm
- *Candidati upgrade:* OmniShotCut (UVA CV Lab, 2026) · TranS4mer · Scene-VLM (Amazon Prime
  Video, 2025) · pyannote-community-1 / NeMo Sortformer · Parakeet v3
