# Verbale — Scene Detector

> **Questo è il verbale delle decisioni, non un piano.** Contiene i numeri misurati, le opzioni
> scartate e — la parte più utile — le affermazioni che si sono rivelate false, con il motivo.
> Unifica gli undici documenti precedenti (`UPGRADE`, `PUNTI-APERTI`, `TRANSIZIONI-GRADUALI`,
> `DA-FARE`, `PLAN_FIXES`, i tre `PLAN (completed)`, le quattro `SESSIONE-*`).
>
> **Leggilo prima di rimettere in discussione una scelta**: `min_scene_len`, la soglia 0,50,
> rimuovere AutoShot, adottare OmniShotCut, il DP penalizzato, MovieNet — sono tutte già state
> misurate almeno una volta, e diverse "ovvietà" sono state smentite dai numeri.
>
> I dati grezzi stanno in `prove/`, che **non è versionata**.
>
> Legenda: ✅ fatto · 🔴 azionabile ora · 🟡 dipende da altro · 🔵 opportunistico · ⛔ deciso, non si fa

---

## Indice

1. [Cronologia](#1--cronologia)
2. [Le regole di metodo](#2--le-regole-di-metodo--gli-errori-che-si-ripetono)
3. [Detection e transizioni](#3--detection-e-transizioni)
4. [Volti e personaggi](#4--volti-e-personaggi)
5. [Scene — il raggruppamento degli shot](#5--scene--il-raggruppamento-degli-shot)
6. [ASR](#6--asr)
7. [Diarizzazione](#7--diarizzazione)
8. [VLM](#8--vlm)
9. [Catalogo, UI, correzione manuale](#9--catalogo-ui-correzione-manuale)
10. [Infrastruttura](#10--infrastruttura)
11. [Ecosistema e licenze](#11--ecosistema-e-licenze)
12. [Deciso — non si fa](#12--deciso--non-si-fa)
13. [Aperto](#13--aperto)
14. [Dove stanno i dati](#14--dove-stanno-i-dati)
15. [Paper di riferimento](#15--paper-di-riferimento)

---

## 1 · Cronologia

| data | cosa |
|---|---|
| 16 lug 2026 | Impianto: TransNetV2 vendorizzato su MPS, PySceneDetect baseline, AutoShot opzionale, splitter ffmpeg, `Scene` con `end_frame` inclusivo |
| — | Catalogo: manifest come backbone, ASR faster-whisper, `align`, UI HTML self-contained |
| — | VLM per shot, resumable, `sample_frames` |
| 17 lug | Telemetria (`core/telemetry.py`), ristrutturazione in package per dominio, galleria multi-film |
| 18-22 lug | Collaudo su *Anna* — il catalogo mente: ASR distrugge metà del parlato, VLM vede colori su b/n, confidence è un flag |
| 22-23 lug | Setup plug-and-play, metriche range-based, benchmark su SHOT, clustering volti a due stadi |
| 23 lug | Audit over-engineering: 4738 → 4347 righe. L'indagine sulle graduali: `runs_to_ranges`, soglia 0,05 |
| 24 lug | Run completo su *Rogue One* (5h16m, 3204 shot). Volti 661 → 113 |
| 25-26 lug | `--faces-refine` (DINOv2 adattato). Vader separato dai trooper: era una soglia. MovieNet: non ripaga |
| 25 lug | Scene grouping (OSG). Annotazione cieca: 38%, sotto il criterio |
| 30 lug | `--diarize`. BBC come secondo banco: l'accordo fra annotatori esperti è **0,630**. I due tratti annotati |
| 30 lug | Il DP penalizzato è k travestito. Novelty pareggia OSG ma la densità non arriva |
| 2 ago | Correzione manuale dei confini nella UI, `--from-manifest`, `start_frame` come identità |
| 3 ago | AutoShot ripristinato **solo come banco di misura**, non ricablato |
| **19 ago** | **Anna: le corse deboli sono flicker del restauro. 0/24 stacchi veri, controlli 12/12** |
| 20 ago | Due altri siti accoppiavano per `index`: il resume dei volti e quello di `caption_manifest` |
| **28 ago** | **`--from-manifest` impone `reencode`** — il taglio manuale scivolava di ~1 GOP. La UI conta i frame sul film, mai sulla clip. Comandi di riproduzione nel player |
| **28 ago** | **La UI diventa uno strumento di lavoro**: quattro viste, coda di revisione per confidenza, scheda del film, salvataggio nel browser, annulla, fusione dei personaggi, EDL/SRT, responsive |
| 23 set | Revisione del codice: `merge_prior` accoppia per **range** e non per inizio; il browser salva **differenze**, non copie; `--from-manifest` conserva confidenza e transizioni; manifest scritto in modo atomico; la confidenza di una graduale è il **picco** della corsa, non la coda |

---

## 2 · Le regole di metodo — gli errori che si ripetono

Sono la parte più riutilizzabile del progetto: **nessuno è stato trovato ragionando**, tutti da
una verifica che *doveva* dare un certo risultato e non lo dava.

| # | errore | come è emerso |
|---|---|---|
| 1 | **Un numero letto senza la sua condizione.** Conteggi di cluster a `min_faces` diverso (1 contro 3) davano un apparente −238% | 168 dei 230 cluster avevano un volto solo |
| 2 | **Un campione troppo piccolo.** «Il default di soglia costa 24 punti di F1»: su 3 video. Su 50 sono **2,8** | scaricando 50 video invece di 3 |
| 3 | **Un offset di un frame.** Il picco di prob cade sull'**ultimo frame dello shot uscente**, non sul primo dell'entrante (96-97% su ~1200 hard cut) | l'IoU degli hard cut faceva 0,35 ≈ 1/3, cioè due intervalli da 2 frame sfalsati di 1 |
| 4 | **Un ground truth sfalsato di un frame.** Il primo frame di un blend `xfade` ha peso 0 sul secondo input: è ancora lo spezzone A, il buco vero è largo `d−1` | `--selfcheck` su due colori uniformi |
| 5 | **Un dato costruito senza la sua condizione.** Gli spezzoni da 4 s di *Rogue One* (ASL 3,04 s) contenevano un taglio vero nel **79%** dei casi, che il GT generato non conosceva | precision 0,04-0,17, troppo bassa per essere vera |
| 6 | **Convenzioni di terze parti.** OmniShotCut emette le transizioni come range espliciti (non buchi), estremo destro **esclusivo**, e gli stacchi netti in `inter` invece che in `intra` | `F1 0,000` su ogni bucket, **hard cut compresi** |
| 7 | **Un rapporto trasferito fra distribuzioni.** Da `n_pred` di ClipShots avevo stimato 5900 shot su *Rogue One*: sono **3788** | misurato invece che estrapolato |
| 8 | **Una media letta senza la sua distribuzione.** «0,05 prende la gran parte del recall»: le graduali larghe sono il **66%** del GT e a 0,05 si mancano quasi tutte | guardando i bucket invece del totale |
| 9 | **Un proxy al posto del path vero.** Tutte le tabelle sulle corse saltavano `enforce_min_len`; la produzione no, e con `min_len=15` i cut andavano **sotto** il default | misurando il path di produzione |
| 10 | **Una metrica che sceglie da sé il punto di lavoro.** `purity_at_k` cercava 3 gruppi, e nello spazio adattato quel numero cade a `t=0,59`, un punto pessimo. A `t=0,70` lo stesso spazio dà 0,98 | confrontando senza soglia (AUC/AP) |
| 11 | **Un default che il banco ri-applicava.** Dopo aver messo `BAND=5` in `optimal_sequence`, il banco che pre-bandava la matrice ri-bandava sopra il default: bande 5, 10, 20 e "nessuna" davano lo **stesso** numero | righe diverse con F1 identico byte per byte |
| 12 | **Il banco e l'utente sulla stessa scheda del browser.** Una misura è uscita contaminata da uno stato di partenza che non era quello che credevo | il banco va su una scheda sua |
| 13 | **Un test rosso che era il test a essere sbagliato.** La lista di scene scritta a mano non copriva tutti gli shot, quindi `contigue: false` era corretto | prima di credere a un fallimento, guardare il banco |
| 14 | **Una spiegazione plausibile scambiata per una misura.** Le clip `copy` di *Anna* durano 2-4 frame più del dovuto: ne avevo dedotto che partissero *prima* del confine, e che fosse quello a spostare i tagli manuali. L'extra sta in **coda**: l'encoder mette un keyframe su quasi ogni stacco, e l'offset in testa è 0 su 14 shot su 15 | misurando la posizione dei keyframe invece della durata, e confrontando in browser il frame del film con quello della clip — hash 8×8 **identico** |
| 15 | **Un controllo che non può fallire non è un controllo.** Cercavo gli elementi che sforano *escludendo* quelli dentro un antenato che ritaglia — ma avevo appena messo `body { overflow:auto }`, quindi **ogni** elemento aveva un antenato che ritaglia e il filtro scartava tutti i candidati. Rispondeva «zero colpevoli» mentre la pagina scorreva di lato | i due numeri non tornavano: 109 px di scorrimento reale contro 0 elementi fuori misura |

> **Il filo comune: un numero troppo netto o troppo storto per essere vero.** Uno zero sugli
> stacchi, una precision a 0,04, un F1 identico su righe diverse. Un risultato *plausibilmente
> mediocre* sarebbe passato — ed è il motivo per cui ogni banco ha almeno un controllo che
> **deve fallire** se il metodo è rotto.

**Tre regole operative che ne discendono:**

1. **Non confrontare numeri fra run con parametri diversi.** Ogni numero va citato con la sua
   condizione (`tol`, `min_faces`, `min_iou`, soglia, numero di video).
2. **La metrica va sempre letta per tipo.** 55 graduali annegate in 2500 hard cut fanno sembrare
   il meanIoU 0,94 quando sulle graduali è 0,21.
3. **Quando la precision non è misurabile, non si riporta.** RAI annota solo i confini di scena,
   ClipShots `only_gradual` solo le graduali: in entrambi un predetto non accoppiato è quasi
   sempre un taglio vero mai annotato. `n_pred` come proxy del costo sì, una precision inventata no.

---

## 3 · Detection e transizioni

### 3.1 · Il difetto e la sua cura

**La diagnosi.** `probs_to_ranges` chiudeva uno shot a **ogni** frame sopra soglia. Durante una
dissolvenza i frame caldi sono molti e consecutivi, quindi produceva una fila di scene da 1 frame
che `enforce_min_len` poi rifondeva: **la larghezza della transizione è nelle `probs` e la
buttavamo noi**. Su una dissolvenza da 24 frame piazzavamo un punto, l'IoU faceva 2/24 = 0,08, e
sotto `min_iou=0,5` non era un TP. Non le mancavamo — le **schiacciavamo**. Ecco perché nessuna
soglia cambiava il risultato: non era taratura, era architettura.

**La cura — `runs_to_ranges`.** Una **corsa contigua** di frame caldi è *una* transizione: lo shot
uscente la include e finisce a `j`, quello entrante parte a `j+1`.

**Il contratto non è stato rotto**, contro la previsione. Si temeva che le corse introducessero
buchi fra gli shot, facendo ricadere `boundary_confidences`, `confidence.reconcile` e lo splitter
(«~30 righe e più rischio»). Non serve: i range restano **contigui e coprono tutti i frame**, e la
larghezza — che prima si buttava — diventa `Scene.transition` e un campo del manifest. Nessuno dei
tre consumatori è stato toccato.

### 3.2 · I banchi di misura

| banco | cosa contiene | cosa misura |
|---|---|---|
| **SHOT** (AutoShot, CVPR-W 2023) | 200 video short-form cinese, 2716 shot, 438 graduali col range | benchmark generale. Scaricato dal mirror HF dei pesi via range HTTP |
| **`xfade` generato** | 300 transizioni da *Rogue One*, 5 tipi × 10 larghezze × 6 | il **tetto**: GT esatto per costruzione |
| **RAI** (AImageLab) | 10 video broadcast, **116 confini di scena** | posizione, non larghezza. Precision non misurabile |
| **ClipShots** `only_gradual` | 257 video, **1634 graduali col range** su 30 video usati | la delimitazione su montato vero |
| **BBC Planet Earth** | 11 episodi, 4855 shot GT, **5 annotatori**, 2745 confini | scene, con l'accordo fra umani |
| ***Anna*** | Portapak 1975 restaurato, 3h33m, 25 fps | il caso patologico: flicker del restauro |
| ***Rogue One*** | 2h14m, montaggio serrato a stacchi netti | il caso normale |

**Dataset cercati e non utilizzabili:** MSU SBD (download da richiedere), OVSD (URL IBM → 404,
nessun mirror delle annotazioni), HF `it-just-works/sbd` (nessuna larghezza), TransVLM
(«coming soon»), MovieNet-SSeg (confini ma niente audio).

⚠️ **Sul download di ClipShots**: 46 GB in tre pezzi su Drive, `b` e `c` bloccati da quota. Ma
`only_gradual` e `test` stanno **entrambi all'inizio del primo pezzo**: ne bastano 18 GB, e dei
257 video estratti restano 2,8 GB. La quota Drive è reale — riscaricare non è dato per scontato.

### 3.3 · I numeri

**Il tetto (`xfade`, GT esatto), `recall / mean IoU` per larghezza:**

| larghezza (frame) | 0 | 1 | 2 | 4 | 7 | 11 | 15 | 23 | 31 | 47 |
|---|---|---|---|---|---|---|---|---|---|---|
| TransNet 0,50 pipeline *(vecchio default)* | .60/.73 | .60/.30 | .33/.58 | .50/.31 | **.00**/.22 | .00/.15 | .00/.11 | .00/.05 | .00/.05 | .00/.02 |
| TransNet 0,05 corse | .60/.71 | .20/.35 | .67/.52 | .70/.59 | .70/.58 | .47/.51 | .37/.41 | .17/.36 | .10/.28 | .03/.21 |
| **TransNet 0,02 corse** | .60/.68 | .10/.31 | .60/.45 | **.87**/.62 | **.80**/.64 | **.67**/.62 | **.57**/.57 | **.57**/.49 | **.30**/.40 | **.17**/.29 |
| **OmniShotCut** | .17/.81 | .07/.34 | .07/.37 | **.80**/**.80** | **.87**/**.86** | **.90**/**.91** | **.80**/**.88** | **.83**/**.89** | **.73**/**.91** | **.57**/**.85** |

**Non c'è nessun muro architetturale.** La pipeline vecchia era a zero da 7 frame in su; con le
corse il recall tiene 0,57 fino a 23 frame — un secondo pieno di dissolvenza.

**Per tipo** (TransNet 0,02 corse): `dissolve` e `fade` tengono 0,83 fino a 23 frame; i **`wipe`
sono il caso perso** — zero sopra i 7 frame, a ogni soglia. Non è delimitazione: un wipe **non
produce un picco di differenza fra frame consecutivi**, la variazione è spaziale. Nessuna soglia
lo cambia. OmniShotCut invece li prende (recall 1,00 a 7/11/15/47 frame).

**Su montato vero (ClipShots, 1634 transizioni), `recall/IoU` per bucket:**

| | cut (n=172) | 4-6 | 7-15 | 16-30 (n=730) | 31-50 | >50 | **R tot** | n_pred |
|---|---|---|---|---|---|---|---|---|
| TransNet 0,50 *(vecchio)* | .81/1.00 | **.00**/.35 | **.00**/.17 | **.00**/.09 | **.00**/.06 | **.00**/.03 | **0,088** | 1518 |
| AutoShot 0,50 | .78/1.00 | .00/.32 | .00/.17 | .00/.09 | .00/.06 | .00/.03 | 0,083 | 1480 |
| **TransNet 0,02 corse** | **.91**/.92 | **.66**/.63 | **.67**/.60 | .32/.41 | .30/.43 | .10/.27 | **0,455** | 3722 |
| **OmniShotCut** | .33/.94 | .17/.63 | .36/**.68** | **.43**/**.73** | **.40**/**.72** | **.62**/**.76** | 0,397 | **1429** |
| corse 0,05 + Omni | **.96** | .57 | .69 | **.56** | .43 | **.62** | **0,606** | 4078 |

**I due profili sono opposti e questa è la scoperta**: stacchi e transizioni strette alle corse
(.91 contro .33), graduali larghe a OmniShotCut (.62 contro .10). Il recall totale li mette
vicini (0,455 contro 0,397) **nascondendo che coprono metà del problema ciascuno**.

**Il path di produzione, non il proxy** (stessi 30 video, `runs_above` include `enforce_min_len`):

| | cut | 7-15 | 16-30 | R tot |
|---|---|---|---|---|
| corse 0,05 *nude* | 0,95 | 0,56 | 0,18 | 0,325 |
| produzione 0,05, `min_len` **15** | **0,77** | 0,33 | 0,11 | 0,215 |
| **produzione 0,05, `min_len` 5** | **0,93** | 0,44 | 0,13 | **0,270** |

### 3.4 · Le due coppie di parametri accoppiati

Entrambe invisibili misurando un parametro alla volta.

- **corse ↔ soglia**: le corse al default 0,50 rendono `+0,002`; abbassare la soglia *senza* le
  corse peggiora tutto (F1 0,255 → 0,076 a 0,02, perché `enforce_min_len` rifonde ogni scena da
  1 frame). Vanno adottate insieme o non conviene nessuna delle due.
- **soglia ↔ `min_scene_len`**: `min_len=15` era stato assolto misurandolo a soglia 0,20-0,50,
  dove i due valori sono equivalenti (+1 punto di F1). A 0,05 la stessa taratura costa **16 punti
  sui cut** (0,77 contro 0,93): nascono più shot brevi legittimi e la fusione cieca ne mangia di
  veri.

### 3.5 · Il default in produzione

`threshold` 0,50 → **0,05** · `min_scene_len` 15 → **5**. Su *Rogue One*, dalle stesse probs:

| | vecchio | nuovo |
|---|---|---|
| shot | 2426 | **3204** (+32%) |
| transizioni graduali registrate | 0 | **461** (mediana 2f, max 22f) |
| VLM stimato | 3,4 h | 4,5 h |
| recall su ClipShots | 0,088 | **0,270** |
| di cui sui soli stacchi netti | 0,81 | **0,93** |

**Il guadagno sui cut non era atteso**: la soglia bassa non serve solo alle dissolvenze, trova
anche stacchi che a 0,50 restavano sotto.

⚠️ **Ma *Rogue One* non ha dissolvenze**: delle 461 transizioni, **406 stanno sotto i 5 frame**
(stacchi con un frame di motion blur) e sopra i 10 frame ce ne sono **cinque in tutto il film**.
Su quel materiale OmniShotCut non ripagherebbe.

⚠️ **Il 25% degli shot ha confidenza sotto 0,2.** È matematico (la confidenza *è* la prob al
taglio, e la soglia è 0,05) e non è un bug: sono gli shot che prima non vedevamo. Ma la UI li
mostra come tutti gli altri. *(23 set: quel 25% era gonfiato — la confidenza di una graduale
leggeva la coda della corsa invece del picco, §9.9. Col picco, su Rogue One, sono il **19,3%**.)*

### 3.6 · *Anna* — il restauro fa tagliare dove non c'è niente (19 ago 2026)

**Il sintomo**: il catalogo vecchio aveva 373 clip, quello nuovo quasi mille. L'ipotesi di
partenza era che togliendo AutoShot fosse venuto a mancare un parere di controllo.

**Falso, e i conti lo dicono subito** (probs in cache, `prove/Anna/probs.npy`):

| | detector | soglia | shot |
|---|---|---|---|
| `manifest.cleaned.json` (vecchio) | ensemble | 0,50 | 373 |
| — | **transnet solo** | 0,50 | **307** |
| `manifest.th005.bak.json` | transnet | 0,05 | 967 |
| `manifest.json` | transnet | 0,12 | 592 |

TransNet da solo alla vecchia soglia fa 307; l'ensemble ne faceva 373. **AutoShot aggiungeva 66
tagli, non li toglieva.** L'esplosione 373 → 967 è **tutta soglia**, zero AutoShot — erano cambiate
due variabili insieme e sembrava colpa della prima.

⛔ **E `confidence.reconcile` non può vetare, per costruzione.** Prende i boundary di `a`, poi
aggiunge tutti quelli di `b` non accoppiati: è un'**unione**. L'ensemble è per forza ≥ max dei due.
Il "secondo parere che fa da freno" non è mai esistito in quel codice: per averlo servirebbe
l'**intersezione**, che è codice da scrivere.

**Il flicker però è reale, e ha una firma che costa zero.** Corse a soglia 0,05, con il picco
della corsa come discriminante:

| | *Anna* (restaurato) | *Rogue One* (pulito) |
|---|---|---|
| corse @0,05 al minuto | 4,70 | 25,46 |
| corse @0,50 (sicure) al minuto | 1,43 | 18,49 |
| **corse deboli** (picco <0,50) **/ sicure** | **2,28** | **0,38** |
| lunghezza mediana delle deboli | 2 frame | 1 frame |

**Sei volte il rapporto.** Non è come si comporta TransNet a soglia bassa in generale: su
materiale pulito le deboli sono un quarto del totale, su *Anna* sono il 70% e più lunghe. Il
restauro fa pulsare l'immagine per qualche frame di fila e il detector legge la pulsazione come
una dissolvenza.

**L'istogramma del picco è bimodale** (1005 corse @0,05): 553 sotto 0,20, valle fra 0,3 e 0,7
(minimo 23 corse nel bin 0,5-0,6), 230 sopra 0,80.

✅ **Annotazione cieca — 24 corse deboli + 12 controlli** (`prove/annota_deboli.py`, seed
20260819, popolazione nascosta in `key.json`, allineamento del seek verificato al **100%** sui
controlli):

| popolazione | giudicati "stacco" |
|---|---|
| controlli (picco ≥ 0,50) | **12/12 = 100%** — l'annotazione è leggibile |
| **corse deboli** (picco < 0,50) | **0/24 = 0%** |

**Separazione perfetta, Fisher a una coda p = 8·10⁻¹⁰.** Nel campione il picco delle deboli
arriva al massimo a 0,294 e quello dei controlli parte da 0,556.

Cosa sono, guardate una per una: pulsazioni di luminanza dentro un'inquadratura ferma, motion
blur, un frame bruciato da fumo o flash in mezzo a una carrellata, corse lunghe (fino a 8 frame)
su un volto che si muove. Nessun montaggio. I 12 veri stacchi del campione erano tutti dei
controlli: stacco su cartello di testo, su nero, su titolo, cambio di inquadratura netto.

⚠️ **Un caso ambiguo** (#18): dropout del nastro, l'immagine va in barre di rumore. Giudicato
"stacco" perché il contenuto cambia davvero, ma non è un taglio di montaggio. È l'unico item su
cui il criterio non è ovvio.

**Conseguenza operativa.** Su *Anna* le **699 corse deboli sono rumore**: scartarle non costa
recall.

✅ **Implementato — `--min-peak`** (20 ago 2026). `runs_to_ranges(probs, threshold, min_peak)`:
una corsa il cui frame più caldo non arriva a `min_peak` non produce un confine e viene assorbita
nello shot. **Il contratto non cambia** — i range restano contigui e coprono tutti i frame.
Quattro righe, tre punti (opzione Typer, campo `Config`, consumatore), tre test.

Perché non basta alzare la soglia, misurato sulle probs vere di *Anna*:

| | shot | graduali ≥3 frame conservate |
|---|---|---|
| `--threshold 0.12` (il catalogo di prima) | 592 | 123 — quasi tutte flicker |
| `--threshold 0.50` (il cerotto) | 307 | **1** |
| **`--threshold 0.05 --min-peak 0.5`** | **307** | **27** |

Stesso numero di shot, ma la soglia alta **schiaccia a un frame** le dissolvenze vere, e sposta 41
confini su 306 (fino a 7 frame). Due domande, due numeri: la soglia delimita, il picco decide se
il taglio esiste.

⚠️ **Default 0,0 — spento, e deve restarlo.** Su *Rogue One* le corse deboli sono 933 e — **non
verificato** — dovrebbero essere in gran parte shot legittimi che a soglia alta non vedevamo. È
una taratura per materiale, non un miglioramento universale. 🔴 **Da fare prima di generalizzare:
la stessa annotazione cieca su *Rogue One*.**

### 3.6 ter · Il catalogo di *Anna* rifatto — e il flicker gonfiava anche il cast

`--all --scenes --n-scenes 35 --threshold 0.05 --min-peak 0.5 --asr-lang it`, **1h34**, otto
stadi verdi. Volutamente da zero su descrizioni, dialoghi e volti: `merge_prior` avrebbe
recuperato le 592 descrizioni vecchie per `start_frame` e il VLM le avrebbe saltate, lasciando
281 shot su 307 con la descrizione della loro **prima metà**.

| | prima (th 0,12) | dopo (0,05 + min_peak 0,5) |
|---|---|---|
| shot | 592 | **307** |
| transizioni registrate | 204, di cui 123 ≥3 frame | 48, di cui **27** ≥3 frame |
| descrizioni | 592 | 306 su 307 |
| shot con dialogo | 394 (67%) | 226 (**74%**) |
| **cast** | **44** | **29** |
| scene | 35 | 35 |

🔑 **Il flicker gonfiava anche il cast, e nessuno l'aveva notato.** A parità di
`--faces-min-shots 3` il cast passa da 44 a 29 personaggi. Il motivo è a valle: uno shot spezzato
in due dal flicker contava **due** shot distinti per il conteggio «ricorre in ≥N shot», quindi
comparse viste una volta sola entravano nel cast. Il taglio è tarato su shot veri e con i falsi
diventa più permissivo di quanto dichiari — un parametro che sembrava indipendente e non lo era.

⚠️ **Un residuo dichiarato: lo shot 251** (263502-274372, 435 s) non ha descrizione. Il VLM non è
andato in errore, ha prodotto **testo vuoto** — e il conteggio diceva solo «306 su 307», senza
dire quale né perché. Ora una generazione vuota viene trattata come fallimento e loggata
(`captioning/caption.py`); il campo resta `None`, quindi un run successivo con `--vlm` lo ritenta
da solo. Un run intero per uno shot non si giustifica: si recupera al prossimo passaggio, o a mano
nella UI che è editabile.

### 3.6 quater · La pipeline scriveva un manifest che il suo validatore rifiuta

Trovato collaudando il catalogo appena prodotto. **`ffmpeg` e `ffprobe` non concordano sul numero
di frame di *Anna***: il decode ne consegna **320737**, `duration × fps` ne dà **320735**. Le
corse vivono sul primo numero, il manifest sul secondo, quindi l'ultimo shot **sforava di 2
frame** — e `_shots_corretti` rifiutava il file:

```
RIFIUTATO: clips/Anna/manifest.json: i range escono dal video (0–320734)
```

Cioè **`--from-manifest` non funzionava su nessun catalogo di *Anna***, che è precisamente il
film su cui si correggono i confini a mano. Il difetto era già nei manifest a soglia 0,12 e 0,05
(non in `manifest.cleaned.json`, perché la vecchia via ensemble passava da `reconcile`, che
clampava a `info.n_frames`), e su *Rogue One* non si vedeva: là i due numeri coincidono.

Fix: `cover_exactly(ranges, transitions, n_frames)` in `detection/neural.py`, chiamata da
`detect_from_frames`. Il numero che vale è quello di `probe`, perché manifest, splitter, miniature
e UI si appoggiano a lui. **Vale in entrambe le direzioni**: se il decode consegna *meno* frame
l'ultimo shot si allunga, invece di lasciare un buco in coda. Due test.

🔑 **Perché non l'aveva preso nessuno**: l'invariante «i range coprono tutti i frame» era
verificata sui range *fra loro* (contigui, dal frame 0) e mai **contro il video**. Un banco che
controlla la coerenza interna non vede un dato che sfora all'esterno.

### 3.6 bis · Due altri siti accoppiavano per `index` — trovati rifacendo *Anna*

La sessione del 2 agosto aveva corretto `merge_prior` e i nomi delle miniature, ma **l'indice
sopravviveva in altri due posti**, e il run a soglia nuova (592 → 307 shot) li avrebbe fatti
sbagliare entrambi:

- **`pipeline.py`, ramo di resume dei volti** — riassegnava `shot["characters"]` per `index`,
  **sovrascrivendo** il recupero corretto che `merge_prior` aveva già fatto per `start_frame`
  poche righe sopra. Su *Anna* avrebbe spostato i personaggi di 356 shot su pezzi di film che non
  li contengono, in silenzio. **Le tre righe erano ridondanti oltre che sbagliate**: `characters`
  è in `CAMPI_COSTOSI`, quindi `merge_prior` lo copre già. Cancellate.
- **`caption_manifest`** — aveva un resume cross-run suo, per `index`. Nel percorso della pipeline
  era **innocuo** (`write_manifest` gira subito prima, quindi rileggeva sé stesso) ma era un
  trappolone latente e anch'esso ridondante con `merge_prior`. Cancellato.

🔑 **La lezione operativa: quando si sposta un'identità, `grep` per l'identità vecchia, non per il
sintomo.** Il fix del 2 agosto era partito da un bug osservato in `merge_prior` e aveva sistemato
i due siti che quel bug toccava. Gli altri due sono rimasti dietro per due settimane, e uno si
sarebbe manifestato solo il giorno in cui il numero di shot cambiava.

### 3.7 · AutoShot — la storia intera

| quando | verdetto |
|---|---|
| impianto | seconda opinione neurale, opt-in, mai nel default |
| dopo la confidence continua | gli resta solo `reconcile`, cioè **aggiungere** boundary in cui TransNet non crede (28% di disaccordo su *Anna*) |
| su SHOT | batte TransNet sulle graduali ≤5f — **ma SHOT è casa sua**: stessa distribuzione, stessa convenzione |
| su RAI | **batte TransNet** (0,836 contro 0,802) a parità di post-processing. Qui la casa non è di nessuno dei due |
| su ClipShots | sulla delimitazione **indistinguibile** (0,083 contro 0,088) |
| ⛔ **rimosso** (30 lug) | annotazione cieca su 40 boundary di *Rogue One*, due annotatori: i boundary che vede **solo lui** sono stacchi veri nel 67% / 40% dei casi contro l'80% / 73% di TransNet. Non paga il +52% di tempo. −922 righe |
| ✅ **ripristinato** (3 ago) | **solo come banco**: modello, predictor, detector, `DetectorKind.autoshot`, `confidence.py`. **Non** ricablati `--ensemble`, `--autoshot-weights`, la via ensemble in `pipeline.py`, il registro pesi |
| ⛔ **e la domanda nuova è chiusa** (19 ago) | serviva come **veto** sul restauro di *Anna*. Ma `reconcile` è un'unione, e sull'ensemble vecchio AutoShot *aggiungeva* 66 tagli. L'obiezione originale resta in piedi: stesso input 48×27, stesso spazio NAS derivato da TransNetV2 → **errori correlati**, e il flicker è nell'immagine |

**Stato del codice, oggi**: `-d autoshot` è cablato in `build_detector` ma `--autoshot-weights`
non esiste in `cli.py`, quindi `cfg.autoshot_weights` è sempre `None` e il comando fallisce con
«pesi mancanti». `confidence.reconcile` ha **zero chiamanti** nel package; `Config.agreement_tol`
ha **zero lettori**. È deliberato — «il wiring si fa se i numeri lo giustificano, non prima» — e
i numeri ora dicono di no.

### 3.8 · OmniShotCut — misurato, complementare, fuori dalla pipeline

- **Gira su MPS** nonostante il README dica CUDA: `engine.py` ha tre `.to("cuda")` senza parametro
  di device, rimappati a runtime (`patch_cuda_to_mps()` in `prove/omni_ab.py`). Nessun kernel
  custom. DETR standard: ResNet18 + 6 layer encoder/decoder, 41M param, input **128×96**,
  finestra 100 frame, 24 query. Checkpoint 164 MB, **MIT anche i pesi**.
- **Costo**: 660 f/s con decode incluso, contro i 390 f/s di *sola* inference di TransNet. Il
  «4× il tempo» che l'aveva fatto rimandare **non regge alla misura**. ⚠️ misurato su 4950 frame,
  da rifare su un film intero.
- **Il vantaggio del paper è metà vantaggio di campo**: sul banco sintetico fa F1 0,680 contro
  0,356, su broadcast reale **pareggia** (0,853 entrambi). È addestrato su una *«fully synthetic
  transition synthesis pipeline»*, cioè la stessa famiglia che `xfade` genera.
- **Sui cut è peggio di noi**: 0,33 contro 0,91.
- **Sulle graduali larghe non ha rivali**: 0,62 contro 0,10 sopra i 50 frame, IoU 0,76 contro
  0,27, e con **1429 predizioni contro 3722**.
- **La union misurata** (dedup a IoU ≥ 0,5): recall 0,606, i cut **non** si degradano (0,96, anzi
  sopra lo 0,95 delle corse da sole), e la sovrapposizione fra i due è solo il 14%. Costo onesto:
  l'IoU di Omni si diluisce (0,73 → 0,58 sulle larghe).
- ⛔ **Fuori dalla pipeline**: dipendenza nuova, venv separato, risoluzione diversa (128×96 contro
  48×27, quindi il decode condiviso non è drop-in), `reconcile` da riscrivere **su range**. E
  **serve materiale con dissolvenze**, che né *Rogue One* né *Anna* hanno.
- 🔵 Se si adotta, arrivano gratis le **etichette di transizione** (`Dissolve`/`Fade`/`Wipe`/
  `Slide`/`Push`/`Zoom`/`Doorway` intra; `Hard_Cut`/`Transition`/`Sudden_Jump` inter): oggi il
  manifest sa *dove* taglia, non *come*.
- 🔵 **`Sudden_Jump`** — scarti da pausa-macchina del Portapak di *Anna*. Nessun detector li modella.

### 3.9 · Il benchmark su SHOT

`scene-detector-benchmark`. Sweep della soglia, 50 video, `tol=5`, `min_scene_len=15`:

| soglia | P | R | **F1** |
|---|---|---|---|
| 0,20 | 0,830 | 0,849 | 0,839 |
| **0,30** | 0,868 | 0,820 | **0,843** |
| 0,50 | 0,885 | 0,755 | 0,815 |

Il vecchio default era 2,8 punti sotto l'ottimo — conservativo, non abbastanza per cambiarlo su
short-form cinese. **Il risultato vero era un altro**: separando i tipi, sulle graduali si era a
**zero** (F1 0,004-0,008, IoU 0,21-0,24) a **ogni** soglia.

**Convergenza notevole**: OmniShotCut dichiara transition IoU 0,192 per TransNetV2; noi ne
misuravamo 0,21 su un dataset diverso. Due misure indipendenti sullo stesso difetto.

⚠️ **Discrepanza interna da conoscere**: due protocolli di matching diversi danno **55** e **89**
graduali sugli stessi 50 video. I numeri delle due tabelle **non sono confrontabili fra loro**.

### 3.10 · `min_scene_len` — misurato e chiuso

La variante "mirata" (non applicare `enforce_min_len` dentro una corsa sopra soglia) produce
output **bit-identico** a `min_scene_len=2`: le uniche scene che nascono dentro una corsa sono
quelle da 1 frame. Le «~5 righe previste» erano zero righe, è un default.

Il guadagno netto era **+1 punto di F1**, non +6: i «+6 punti di recall» venivano pagati con
−1,5 di precision, e su un F1 la precision pesa quanto il recall. `min_len=1` è **peggio** di 15
a soglia bassa (−0,058): l'ottimo sta fra 2 e 5, non al minimo.

---

## 4 · Volti e personaggi

### 4.1 · Clustering a due stadi

Clusterizzare i singoli volti dell'intero film spezza una persona in più identità: su *Anna*
1634 volti → **68 cluster** per una decina di presenze reali.

⛔ **ByteTrack non si applica.** Il tracking IoU + Kalman presuppone video **denso**; noi
campioniamo 6 frame sparsi per shot via seek, e fra un campione e l'altro un volto attraversa
l'inquadratura. Non c'è continuità geometrica su cui agganciarsi.

L'equivalente che regge con frame sparsi:
- **stadio 1** — greedy dentro ogni shot con **must-not-link per frame**: due volti nello stesso
  fotogramma non possono finire nello stesso gruppo, per quanto si somiglino. È il vincolo che
  impedisce a un campo/controcampo di collassare in un'identità sola;
- **stadio 2** — `cluster_faces` sugli embedding **mediati** dei gruppi, ordinati per numerosità
  (i gruppi grandi come seed, più affidabile del singolo volto più nitido).

**Validato su *Anna***, a parità di `min_faces`:

| `min_faces` | baseline | due stadi | delta |
|---|---|---|---|
| **3** | 68 cluster · 243 shot | **47 · 238** | **−31% cluster**, −2% copertura |
| 5 | 42 · 241 | 34 · 233 | −19%, −3% |
| 10 | 27 · 227 | 21 · 224 | −22%, −1% |

I frammenti riassorbiti si vedono nei cluster grandi: la protagonista 73 shot/209 volti →
**76/262**. Pre-filtro `min_face_px=50` applicato **prima** di clusterizzare: nel cinema gran
parte delle detection sono volti lontani o di scorcio, il cui embedding è rumore.

### 4.2 · Il taglio del cast — l'asse era sbagliato

Su *Rogue One* il run produceva **661 personaggi, 548 con un solo shot**. `min_faces` contava le
*detection*: un volto in 2 frame di un solo shot passava. **Un personaggio del cast è chi ricorre
fra gli shot**, non chi ha molte detection. Il taglio è diventato `--faces-min-shots`:

| soglia | cast su *Rogue One* |
|---|---|
| min_faces ≥ 2 (per volti) | 274 |
| min_shots ≥ 2 | 113 |
| **min_shots ≥ 3** (default) | **65** |

**La soglia di clustering non era il problema**: i ricorrenti (≥3 shot) sono ~65 stabili da 0,3 a
0,6. Abbassarla toglie solo singleton. Lasciata a 0,5.

### 4.3 · Il cluster dei non-volti

Segnalato guardando il catalogo: «Personaggio 23» unisce persone diverse, e l'unico filo è che
**o sono droidi o hanno elmetti**. Confermato: cluster **22**, 259 volti in 93 shot, contiene
K-2SO, Darth Vader, gli stormtrooper, un pilota con visiera e una creatura pelosa. ArcFace è
addestrato su volti umani scoperti; su questi produce embedding che descrivono «oggetto scuro a
forma di testa», non identità.

**Tre rimedi plausibili, tutti smontati dalla misura:**

| ipotesi | esito |
|---|---|
| il cluster è *lasco*, si becca dalla coesione | ❌ 0,722 contro 0,746 mediano: **normale** |
| sta in una regione "generica" dello spazio | ❌ cos(centroide, media globale) 0,283, in mezzo ai legittimi (0,14-0,69) |
| alzare `--faces-min-score` | ⚠️ accusa ma non separa |
| stringere la soglia di clustering | ⚠️ scambia fusione con frammentazione |

- **`det_score` è un buon rilevatore di cluster sospetti e un pessimo separatore.** Mediana 0,579
  contro 0,762 degli altri, e il p90 del 22 (0,68) sta **sotto il p10 di ogni cluster legittimo**
  (0,69). Ma *dentro*, K-2SO compare a 0,50 **e** a 0,81. Alzare la soglia a 0,65 taglia l'82% del
  cluster, costa il 12% di tutti i volti del film, e lascia comunque K-2SO e Vader insieme.
- **Nessuna soglia di clustering funziona.** A 0,55 si spacca in 120/55/34/31: il gruppo da 55 è
  K-2SO puro, ma quello da 120 è ancora K-2SO + Vader + trooper + pilota.

**Il danno vero non è la card sbagliata**: il nome del cluster entra nel prompt del VLM, quindi
93 shot verrebbero descritti citando un personaggio inesistente.

✅ **Si marcano, non si scartano.** `recognition/faces.mark_uncertain`: mediana di `det_score` per
cluster, sotto `UNCERTAIN_DET = 0,65` il cluster prende `uncertain: True`. Conseguenze: **fuori
dal prompt del VLM** e segnalato nella UI (card in trasparenza, `⚠`, tooltip). Resta visibile e
rinominabile — il giudizio su chi sia davvero lo può dare solo una persona.

Su *Rogue One*: **10 personaggi su 65** segnati, **174 shot** perdono un nome nel prompt. La
soglia cade fra 0,638 e 0,653, ed è il punto più arbitrario della faccenda.

### 4.4 · Il raffinamento a due stadi — `--faces-refine`

ArcFace resta primario; i **soli** cluster che `mark_uncertain` segnala vengono rimessi in
discussione su ritagli di **figura** con DINOv2 (ViT-L con register, Apache 2.0) più una testa
lineare addestrata sul film. Gli umani non passano di qui per costruzione.

**Due strade provate e bocciate prima di arrivarci**, entrambe con la misura:

- ⛔ **DINOv2 grezzo sui ritagli di figura.** Nessuna soglia funziona: sotto 0,85 fonde i due
  protagonisti umani, sopra li polverizza (240 ritagli → 205 gruppi). ArcFace, per confronto, non
  li confonde **mai**, a nessuna soglia. Le contact sheet confermano che i ritagli sono buoni: non
  è geometria, è che il coseno di DINOv2 non è allineato all'identità.
- ⛔ **Adattatore contrastivo auto-supervisionato «stesso shot = stessa identità».** Sembra
  gratis: il 77% degli shot ha un volto per frame campionato, 14 214 coppie positive senza
  tracking. **Peggiora**: 240 ritagli → 71 gruppi. Il motivo è aritmetico — **8 191 positivi
  dichiarati contro 2 676 785 coppie della stessa identità finite fra i negativi** (17,7% di
  tutte le coppie). La testa impara l'identità dello *shot*, non del personaggio.
  - 🔑 **E vale anche per le tracce: una traccia non attraversa uno stacco.** Da dentro lo shot
    non arrivano positivi cross-shot, mai. Chi propone i body-track deve rispondere a questa riga.

**Quello che funziona, e non costa dati esterni**: i cluster ArcFace **affidabili** del film fanno
da maestri. Sui volti umani scoperti ArcFace lega correttamente attraverso gli stacchi, quindi dà
positivi cross-shot veri e gratis (su *Rogue One*: 21 identità maestre, 130 196 coppie). L'ipotesi
che regge: *ciò che varia fra uno shot e l'altro — luce, posa, scala, sfondo — è proprietà della
fotografia del film, non del personaggio*, e imparato sugli umani si applica anche ai non-umani.
Effetto isolato: a parità di cattura, i gruppi sui due protagonisti passano da **20 a 7**.

**Non serve un character bank** — che esiste per Star Wars e non per *Anna*, e questo percorso
funziona identico sui due.

**Risultato**: 65 → 69 personaggi. Il cluster 22 si scompone in 175 + 84, l'85 in 55+17+9+5. I
cluster umani restano identici volto per volto. Costo: +23 min di embedding, **nessuna estrazione
ffmpeg in più**.

### 4.5 · Vader separato dai trooper — era una soglia, non un modello

**Il difetto stava in una riga**: `_refine` riusava `faces_threshold` (0,50), tarato sullo spazio
**ArcFace**, per clusterizzare nello spazio **DINOv2 adattato**. Le due distribuzioni di
similarità non sono commensurabili.

Misurato con verità annotata a mano (84 ritagli: 36 Vader, 35 stormtrooper, 13 altro):

| | t=0,50 (spedito) | **t=0,70** (corretto) |
|---|---|---|
| #661 | 84 misti | **36, tutti Vader** |
| #662 | — | **26, tutti stormtrooper** |
| **purezza pesata** | **0,43** | **0,98** |
| cluster 22 si scompone in | 2 gruppi | **9 gruppi** |

Da qui `Config.faces_refine_threshold` (default **0,70**), separato di proposito: **due spazi di
embedding diversi non condividono una soglia**.

⚠️ *Trooper A contro trooper B* non è separabile da nessuna feature visiva — sono identici per
progetto, e VGG dichiara lo stesso limite. I trooper puri ma **frammentati** vanno bene così.

### 4.6 · MovieNet — scaricato, addestrato, non ripaga

L'ipotesi: la testa ha 21 identità maestre di un film solo, con **3 087 identità su 573 film**
dovrebbe andare molto meglio. Fatto per davvero: 162 GB di keyframe, 187 404 ritagli di corpo,
154 minuti di embedding, SupCon a campionamento P×K (48×4; il full-batch avrebbe voluto una
matrice 187k×187k, ~140 GB).

Valutazione **senza soglia** sulle coppie cross-shot, perché confrontare la purezza di due spazi
alla stessa soglia coseno non vuol dire niente:

| spazio | AUC | AP |
|---|---|---|
| DINOv2 grezzo | 0,944 | 0,951 |
| testa per-film (21 maestri) | 0,944 | 0,940 |
| **testa MovieNet (3 087 maestri)** | **0,948** | **0,956** |

**+0,004 di AUC per 162 GB e mezza giornata.** L'ipotesi «serve più supervisione» è smentita: il
collo di bottiglia non erano le feature né la quantità di maestri — **era la soglia**.

📌 **L'errore di metodo che ne è uscito**: `purezza@3gruppi` faceva concludere che la testa
per-film *danneggiasse* la separazione (0,52 contro 0,96). Falso — `purity_at_k` cercava 3 gruppi,
e nello spazio adattato quel numero cade a t=0,59, un punto di lavoro pessimo. A t=0,70 lo stesso
spazio dà 0,98.

**Verificato prima di scaricare**, e i due dubbi erano infondati:
- box **di corpo** con identità: **808 051** su **630** film, **3 349** identità uniche (attori
  IMDb). Zero box di volto: è un dataset di corpi;
- «l'identità è l'attore accreditato, quindi i mascherati non ci sono» → **falso**. Fuori da Star
  Wars: ~35 film, ~45 identità, ~11 000 istanze fra maschera integrale (Spider-Man, Rorschach, V,
  Batman, Jason), protesi (Hellboy, Edward mani di forbice, Penguin), mocap e CG (Jake Sully,
  Neytiri, Caesar), robot (Terminator, T-1000, David), trucco pesante (Joker, Freddy). In Star
  Wars: Vader 225, C-3PO 281, Chewbacca 272, **R2-D2 71** — un droide senza volto né geometria
  umana, annotato;
- «i keyframe a 240p sono troppo piccoli» → **falso**: i box di corpo occupano il 93% dell'altezza
  del frame (mediana), quindi il ritaglio mediano è alto ~223 px e l'input di DINOv2 è 224.

⚠️ Ma la parte non-umana è **modesta**: ~11 000 istanze su 808 051. Il valore sarebbe
l'**invarianza** imparata dalle 3 349 identità su 630 fotografie diverse. Dati in
`datasets/movienet/` (hard link, zero spazio in più), accesso in `prove/movienet.py`.

### 4.7 · Il soffitto non è DINOv2 — è la supervisione

Un probe lineare **supervisionato** sugli embedding DINOv2 **grezzi** separa Vader dai trooper a
**1,00**:

| misura | esito |
|---|---|
| CV per shot, 5 fold | **1,00 ± 0,00** |
| holdout **per contesto** (A→B e B→A) | **1,00** |
| etichette permutate per shot (controllo) | **0,50 ± 0,18** (max 0,77) |

Le due righe di controllo servono entrambe: l'holdout per contesto addestra su Vader nel corridoio
scuro + trooper in pieno sole e testa su Vader nello spazio + trooper in un interno rosso — se il
probe avesse imparato la *scena* invece dell'identità, lì crollava. E 1,00 con 1024 feature su 71
campioni è sospetto per pura aritmetica, ma con le etichette permutate scende a 0,50.

**L'informazione c'è già negli embedding che calcoliamo**, e il clustering non la sfrutta.

### 4.8 · Encoder di apparenza — complementari, non sostitutivi

SigLIP grezzo sui ritagli (360 immagini):

| soglia | cluster 22 (non-volti) | due protagonisti **umani** |
|---|---|---|
| 0,80 | 1 gruppo: non separa | 1 gruppo, purezza 0,50: **fonde i due** |
| 0,85 | **55 / 37 / 15**: separa | purezza 0,97, 2 gruppi ancora misti |
| 0,90 | 60 / 16 / 14 | purezza 1,00 ma **35 gruppi per 2 persone** |

Le contact sheet: gruppo 0 = elmetti (trooper *e* Vader insieme), gruppi 4 e 5 = K-2SO, separati
fra loro **solo dall'illuminazione**. **ArcFace è ottimo sui volti umani e catastrofico sui
non-volti; SigLIP l'opposto.**

⛔ **L'ibrido ArcFace + SigLIP scambiava un cluster sbagliato con tre cluster sbagliati.**
⚠️ **Superato in parte**: il difetto era **l'encoder, non lo schema** — con DINOv2 adattato K-2SO
non si spacca più per illuminazione. Resta vera la parte su Vader fuso coi trooper a t=0,50.

### 4.9 · Il VLM come verificatore, non come battezzatore

Provato con Qwen3-VL-8B-4bit, 4 ritagli per cluster, due domande.

**La verifica è 5/5**: i due cluster incerti riconosciuti come misti, i tre legittimi come puri.
**Il nome no**: K-2SO diventa C-3PO, e due cluster con **coseno 0,101** fra i centroidi — due
volti completamente diversi — prendono lo stesso nome. Non è frammentazione, è allucinazione.

**Misurato sul serio** con un ground truth **costruito** (un gruppo di ritagli da un solo cluster
è puro *per costruzione*, uno che ne mescola due è misto *per costruzione*):

| banco | misto | puro | nomi «non lo so» |
|---|---|---|---|
| *Rogue One*, 40 casi | **20/20 = 100%** | 16/20 = 80% | **39/40** |
| *Anna*, 12 casi (misto soltanto) | **10/12 = 83%** | — | **12/12** |

✅ **L'obiezione «su un film ignoto allucina» non regge — ma solo con il prompt giusto.** *Anna* è
l'opposto di un blockbuster e il modello **non ha inventato un solo nome**. L'allucinazione del
pilota veniva dal prompt, che diceva *«un algoritmo sostiene che siano lo stesso personaggio»* e
poi chiedeva i nomi: **suggerire una conclusione basta a farla confermare**.

**Il prezzo**: col prompt onesto smette anche di azzeccare *Jyn Erso*. Non c'è un prompt che dia
nomi affidabili — **verificatore sì, battezzatore no**, misurato due volte in due direzioni.

⚠️ Le due righe della tabella **non si confrontano fra loro**: *Anna* usa 2 miniature piccole,
*Rogue One* 4 ritagli a 640 px.

### 4.10 · Ricognizione — cosa dice lo stato dell'arte

**Coincide con la nostra diagnosi.** VGG Oxford, *Character-Centric Understanding of Animated
Movies* ([arXiv 2509.12204](https://arxiv.org/html/2509.12204), set 2025), su 75 film animati: i
personaggi non umani mandano fuori strada il riconoscimento facciale, e la risposta è cambiare
**feature**, non tarare. Usano **DINOv2 su ritagli di corpo** + voce **ECAPA-TDNN** + tracce da
SAM2: **81,8 AP contro 45,3 di InsightFace**, cioè contro il nostro stesso rilevatore.

Prima di loro, **VPCD** — Brown, Kalogeiton, Zisserman,
[*Face, Body, Voice*](https://arxiv.org/pdf/2105.09939) (ICCV-W 2021,
[codice MIT](https://github.com/Andrew-Brown1/Video_Person_Clustering)): clustering multimodale
con face-track, body-track e voice-track, 35 396 face-track su 23 h. **È da lì che deve venire la
metrica di purezza** che ci manca.

**La terza strada è la voce**, e converge con la diarizzazione già in programma: K-2SO e Vader
hanno voci inconfondibili proprio dove il visivo fallisce. ⚠️ **Limite da mettere in conto:**
funziona solo su chi parla — gli stormtrooper restano indistinguibili.

### 4.11 · Aperto sui volti

- 🔴 **Purezza vera del raffinamento.** I numeri sono conteggi e un colpo d'occhio su 16 ritagli.
  Annotare i 259 del cluster 22 chiuderebbe la domanda. Metrica: VPCD.
- 🔴 **Cast stantio nel catalogo.** `clips/Rogue.One/manifest.json` ha 113 personaggi da un run con
  `min_shots=2`; il default è 3 e darebbe 65. Il ramo di resume riusa `prior["cast"]` **senza
  controllare con quali parametri era stato costruito**: rilanciare con parametri diversi non
  ricalcola. Serve almeno registrare i parametri accanto al cast.
- 🟡 **Frammentazione 22↔85** (coseno 0,764, stesso volto in due cluster). Il greedy a passo
  singolo non li fonde: serve un secondo merge sui centroidi finali.
- 🔵 **Recall, non solo purezza.** 1634 volti su 3h33m di *Anna* sono pochi: molte presenze mai
  viste. Il raffinamento riduce i falsi cluster ma non recupera chi non è mai stato rilevato —
  VPCD usa i **body-track** per questo.
- 🔵 Il cluster 85 spezzato in 4 (55/17/9/5) e nessuno ha guardato cosa siano.
- 🔵 I cluster raffinati restano `uncertain`, quindi fuori dal prompt VLM. Deciso di proposito: se
  un cluster raffinato è puro il suo «Personaggio N» non è più un nome sbagliato, ma è una
  decisione da prendere con la purezza in mano.
- 🔵 **Provino del cast come output stabile.** La contact sheet dei cluster è stata lo strumento
  diagnostico migliore di tutto il progetto; oggi è uno script usa-e-getta
  (`prove/faces_sheet.py`, legge le label da `/tmp/lab.npy`).

---

## 5 · Scene — il raggruppamento degli shot

### 5.1 · Il metodo: OSG, e perché non un clustering

*Optimal Sequential Grouping* (Rotman, Porat, Ashour, IBM 2016): programmazione dinamica che cerca
il partizionamento a blocchi **contigui** di costo intra-blocco minimo su una matrice di distanze
fra shot. Due proprietà per cui è preferito a un clustering:

- **la contiguità è nella formulazione**, non un vincolo aggiunto dopo. Il montaggio alternato e
  il metodo di copertura (la stessa situazione da più angolazioni) sono esattamente i casi in cui
  un clustering per somiglianza visiva sbaglia;
- **non è addestrato**: nessun peso, nessuna dipendenza oltre numpy.

Firme = **istogrammi HSV sui frame 48×27** che il detector legge già. Il segnale più povero
possibile, deliberatamente: OSG è agnostico alle feature, quindi se la misura dice che non basta
si sostituisce `shot_signatures` e il resto non cambia.

### 5.2 · La banda — il guadagno più grande della campagna

`H_add` come sta nell'articolo somma **tutte** le distanze dentro un blocco, cioè pretende che lo
shot 1 di una scena somigli al suo shot 40. Le scene vere derivano — cambia la luce, ci si sposta,
entra un personaggio — e quel prior le spezza. Bandare a W shot toglie il prior globale.

| variante | RAI @5 | RAI @25 | BBC (mediana 5 annot.) | % accordo umano |
|---|---|---|---|---|
| H_add senza banda | 0,259 | 0,328 | 0,242 | 38% |
| banda 3 | — | — | **0,317** | **50%** |
| **banda 5** (in uso) | **0,310** | **0,388** | 0,300 | 48% |
| banda 10 | 0,276 | 0,345 | — | — |
| H_nrm | 0,276 | 0,345 | — | — |
| H_nrm banda 10 | 0,086 | 0,103 | — | — |

Migliorano **tutti e cinque** gli annotatori BBC; McNemar appaiato senza banda vs W=5 dà
**p < 0,01 su 4 su 5** (il quinto nella stessa direzione). Curva unimodale su entrambi i banchi,
che si appiattisce quando W supera la scena media: è il meccanismo atteso, non un picco casuale.

**W=5 e non 3**: 3 vince su BBC di 0,017 ma su RAI ricade esattamente sul valore di «nessuna
banda» (−0,060). 5 è ottimo su un banco e a un soffio sull'altro.

### 5.3 · 🎯 Il numero che mancava: l'accordo fra umani è 0,630

Da BBC Planet Earth, dalle sole annotazioni e senza nemmeno i video: F1 mediana fra coppie di
annotatori **0,630** (min 0,461, max 0,678, 10 coppie). E i cinque marcano da **327 a 706**
confini sugli stessi 11 episodi: **2,2× di scarto su quante scene ci siano**.

- **Il bersaglio non è F1 1,00, è ~0,63.** Ogni numero del progetto va letto come frazione di quello.
- «non sono un esperto di cinema e potrei sbagliare» era **giustificato e non era il problema**:
  gli esperti fra loro stanno a 0,63.
- La stima automatica di k non fallisce solo per debolezza dell'euristica: **un k vero non
  esiste**.

**Perché BBC è meglio di RAI**: gli shot sono ground truth (si misura il *raggruppamento* senza il
soffitto della detection, che su RAI era 0,89 di recall a tol 5), e confini e predizioni sono in
**indici di shot**, non in frame — niente tolleranza da citare.

### 5.4 · SigLIP non batte gli istogrammi

| metodo | F1 @tol 5 | F1 @tol 25 |
|---|---|---|
| soffitto del detector (recall) | 0,888 | 0,983 |
| casuale (20 seed) | 0,094 | 0,126 |
| uniforme | 0,095 | 0,103 |
| **istogrammi HSV** | **0,259** | **0,328** |
| **SigLIP centrato** | **0,284** | **0,353** |

33 confini trovati contro 30 su 116; McNemar esatto **p = 0,68**. Tre confini di scarto: rumore.
Il segnale c'è (entrambi a 2,7-3,5× il casuale, e l'uniforme non stacca il casuale, quindi il
banco non è vincibile a caso), e non è colpa della detection.

- **SigLIP è anisotropo**: coseno 0,993 intra contro 0,934 inter su rumore. Togliere la media vale
  **+0,034** su SigLIP e **−0,018** sugli istogrammi.
- ✅ **La premessa mai verificata è verificata**: `siglip2-base-patch16-224` gira su MPS a **104
  img/s**. End-to-end però si scende a 13-15 img/s: il collo di bottiglia sono i **3 seek ffmpeg
  per shot**, non l'inferenza.
- Gotcha `transformers` 5.x: `get_image_features` torna un `BaseModelOutputWithPooling`, non un
  tensore. Serve `.pooler_output`.

**La conclusione che conta**: due famiglie di feature lontanissime — istogrammi di colore e un
encoder vision-language — cadono **dentro il rumore l'una dell'altra**. Il tetto non è nella
rappresentazione, è **nel metodo**.

`siglip_signatures` + `transformers` **restano** nell'extra `neural` (deciso 25 lug): hanno perso
la misura ma rifarli costerebbe più che tenerli. **Non sono nel percorso della pipeline.**
⚠️ La ragione dichiarata per tenerli era BaSSL, **che nel frattempo è stato chiuso** (§5.5): la
giustificazione è scaduta.

### 5.5 · BaSSL e OVSD — due porte chiuse

⛔ **BaSSL non è adottabile senza addestrarlo.** Dal Model Zoo, verbatim: «We provide pre-trained
checkpoints trained in a **self-supervised** manner. **After fine-tuning** with the checkpoints,
the models will give scores…». Tutti e cinque i checkpoint sono pre-training: adottarlo significa
finetunare su MovieNet-SSeg, cioè esattamente il criterio con cui erano stati scartati TranS4mer e
Scene-VLM. In più `pytorch==1.7.1+cu110`, `pytorch-lightning==1.3.8`, CUDA 11.0, nessun percorso
di inferenza documentato.

⛔ **OVSD non è più scaricabile**: `research.ibm.com/haifa/projects/imt/video/…` → 404, nessun
mirror delle annotazioni. I video sono CC e si troverebbero, le annotazioni no.

⛔ **TranS4mer**: *Pre-trained Models: **TODO***. Nessun checkpoint. «Adottarlo» significa
addestrarlo.

⛔ **Lo zero-shot non funziona.** Chiedere a un VLM di raggruppare senza fine-tuning: Qwen2.5-VL-7B
fa **11,1 F1**, Claude Sonnet 4.5 fa 37,6, contro i 62,1 del modello addestrato. Non c'è
scorciatoia via prompt.

📌 **Dall'ablation di Scene-VLM**: solo visivo → 58,6 F1; con sottotitoli + identità personaggi →
62,1. Cioè dialoghi e personaggi — le due cose che verrebbe voglia di cablare per prime perché ce
le hai già — valgono **~3,5 punti in tutto**.

### 5.6 · L'annotazione cieca — 38%, contro una soglia di 70%

33 confini proposti + 33 non-confini giudicati, annotatore singolo, `key.json` nascosto:

| popolazione | n | giudicati "scena diversa" |
|---|---|---|
| confini da sola OSG | 26 | **10 = 38%** |
| confini forzati dalla punteggiatura | 7 | **0 = 0%** |
| non-confini (controllo casuale) | 33 | 5 = 15% |

**Il segnale visivo esiste** — 38% contro 15% è Fisher a una coda p = 0,041 — **ed è troppo
debole**. Per il criterio fissato *prima* di misurare (≥70%) la conclusione è pre-registrata: le
feature non bastano, non «si ritocca k».

⛔ **Il correttivo della punteggiatura è stato provato e tolto.** Il manuale dà
dissolvenza/tendina/iris come marcatori di blocco narrativo e `Scene.transition` sembrava offrirli
gratis. Due misure indipendenti dicono di no: dei 461 `transition` di *Rogue One* **279 sono da 2
frame** (stacchi netti per costruzione), solo 35 arrivano a ≥6; e i confini forzati da quelle 35
— comprese una da 10 e una da 13 frame — sono stati giudicati **0/7 cambi di scena**, *sotto* il
15% dei controlli casuali. Il campo dice dove il detector ha visto una corsa calda, non che lì ci
sia una dissolvenza. **Riaprire solo con un detector che tipizza le transizioni.**

⚠️ **Due limiti di quel banco, per non ripeterli**: mancava un **controllo positivo** (i controlli
erano *non*-confini, che non garantiscono nulla — quindi non c'era modo di distinguere «OSG
sbaglia» da «l'annotazione è rumorosa»); e il 15% sui controlli implicava una scena ogni 16 s, che
non è la "scena" del manuale.

### 5.7 · I due tratti annotati stacco per stacco — e la densità dipende dal materiale

Il protocollo che mancava: **tutti** gli stacchi di un tratto continuo, non un campione.

| tratto | shot | stacchi | confini certi | tasso | una scena ogni |
|---|---|---|---|---|---|
| **azione** (3600-4500 s, Eadu) | 1393-1753 | 360 | **4** (+5 incerti) | **1,1%** | ~180 s |
| **dialogato** (2700-3600 s, Jedha→Eadu) | 991-1392 | 401 | **12** (+10 incerti) | **3,0%** | ~69 s |

Il tratto dialogato è stato scelto **prima di guardare** come la finestra da 900 s con più parlato
del film (1160 parole ASR contro 502).

🎯 **Il 15% dell'annotazione campionata era un artefatto**: 13× di scarto.

⚠️ **E ribalta la conclusione su k.** Si era scritto che i 126 di *Rogue One* fossero «con ogni
probabilità una forte sottostima»: sul tratto annotato è **il contrario**. OSG mette 35 confini
dove ce ne sono 4 (9×), e il manifest gira a k=250. Un k giusto sarebbe ~30-45 scene.

| OSG contro i confini certi | tol 0 | tol 1 | tol 3 |
|---|---|---|---|
| azione (4 confini) | F1 0,051 | **F1 0,205 (P 0,11 · R 1,00)** | F1 0,205 |
| dialogato (12 confini) | **F1 0,308** | F1 0,385 | **F1 0,538 (P 0,50 · R 0,58)** |

**Il recall è 1,00 a tol 1 sul tratto d'azione: OSG trova tutti e quattro i confini veri.** Non gli
manca il segnale, gli manca la **parsimonia** — 31 confini di troppo su 35. Diagnosi diversa da
«le feature non bastano», e indica dove intervenire: **k**, non le firme.

**Dove k è nell'ordine giusto OSG arriva a 0,54-0,56**, cioè all'86% dell'accordo fra annotatori
esperti. **Un k unico per il film è troppo alto per l'azione e troppo basso per il dialogo.**

⚠️ Limiti dichiarati: un annotatore non esperto, e un tratto d'azione ha per costruzione scene
lunghe.

### 5.8 · Densità variabile — due metodi indipendenti, stesso fallimento

⛔ **Il DP penalizzato è k travestito.** `C[e] = min_m C[m] + cost[m,e] + λ` (change-point
penalizzato, Killick 2012), λ in unità del costo tipico di uno shot.

- Su BBC **pareggia l'oracolo e non lo batte**: F1 0,294 contro 0,300 del k oracolo (che conosce
  il numero di scene *per episodio e per annotatore*) — ma con **1890 confini contro 549**.
- Sui due tratti la densità **non varia**: rapporto 1,14 / 1,04 / 0,90 a λ crescente, dove il vero
  è **3,0**.

🔑 **Il perché è meccanico**: con la banda, il costo di un blocco è ~proporzionale al numero di
shot che contiene (ogni shot pesa ~W distanze). Il guadagno di spezzare è simile ovunque, e un λ
costante produce una densità costante. **La penalizzazione sposta il totale dei confini, non la
loro distribuzione.**

⛔ **Novelty a contrasto locale — competitivo, ma la densità non arriva.** Kernel scacchiera
(Foote 2000) sulla stessa matrice, più soglia **adattiva** (`media + z·std` su finestra
scorrevole). Criteri fissati prima: F1 ≥ 0,300 su BBC, rapporto di densità ≥ 2,0.

| banco | OSG (k oracolo) | novelty | |
|---|---|---|---|
| BBC, 5 annotatori | 0,300 | **0,302** (518 confini contro 549 GT) | pari |
| RAI, tol 5 / tol 25 | **0,310 / 0,388** | 0,266 / 0,319 | **OSG** |
| *Rogue One* dialogato, F1@0 / @3 | 0,333 / 0,583 | **0,370 / 0,667** | novelty |
| *Rogue One* azione, F1@0 / @3 | 0,000 / 0,000 | **0,100 / 0,300** | novelty |

Nessuno domina, e il parametro migliore cambia col banco: **non c'è taratura unica**. Notevole:
OSG con k oracolo sul tratto d'azione fa **0,000** — con 4 confini imposti non ne azzecca nessuno
nemmeno a tol 3, mentre con k=250 globale li trovava tutti e quattro a tol 1 sommergendoli in 31
falsi. Il pregio strutturale di novelty resta che **non chiede k**.

⛔ Ma la densità non varia neanche qui: 15 confini nel dialogato e 16 nell'azione (rapporto 0,94).
Su **tutte e dodici** le combinazioni provate il rapporto sta fra 0,59 e 1,12.

🔑 **L'ipotesi da abbandonare è un'altra.** Non è il DP a essere sbagliato, e non è il
partizionamento globale: **le feature visive di basso livello non contengono la densità di scene**.
In una battaglia i cambi di inquadratura sono frequenti e contrastati quanto in un dialogo —
cambia il *significato*, non la fotografia. Coerente con §5.4, dove SigLIP non batteva gli
istogrammi: nemmeno lui vede la differenza fra «nuova scena» e «nuova inquadratura della stessa
scena».

🔴 **Dove guardare adesso**: le **descrizioni VLM sono già nel manifest** (3204 su *Rogue One*,
gratis). Un confine di scena dovrebbe corrispondere a un cambio di *argomento* nel testo, e il
testo distingue «esplosione nell'hangar» da «Jyn parla con Cassian» in un modo che un istogramma
non può. Prima misura senza scrivere quasi niente: distanza fra descrizioni adiacenti (TF-IDF o
embedding) contro i due tratti annotati, e vedere se **il rapporto di densità si avvicina a 3,0**.
Se neanche lì, la densità variabile non è ottenibile da questo tipo di segnale e va chiusa.

### 5.9 · La voce non predice i confini — li anti-predice

Sul tratto più dialogato di *Rogue One*:

| categoria | coppie | confini | tasso |
|---|---|---|---|
| dominante **cambia** | 44 | **0** | **0,0000** |
| parlanti condivisi | 166 | 5 | 0,0301 |
| almeno uno **muto** | 191 | 7 | **0,0366** |

**Zero confini su 44 cambi di parlante**, e il tasso più alto è fra gli shot muti. Col senno della
misura è ovvio: un cambio di parlante *è* il campo/controcampo, cioè il segnale più forte di
**continuità** dentro una scena; un cambio di scena cade su una **pausa**.

⛔ **E l'indizio di RAI non generalizza.** Là «cambia chi parla di più» dava 1,74× (p = 0,017), ma
il dominante è il conduttore e cambiarlo coincide con lo stacco didattico fra segmenti. Su fiction
il meccanismo non esiste. **È il caso da manuale del perché servono due banchi prima di credere a
un effetto.**

⚠️ Anche su RAI il risultato era fragile: la formulazione letterale («condividono almeno un
parlante») **satura** — 853 coppie su 1225 contro 28 disgiunte, potenza nulla; e «cambia il
dominante» era la seconda operazionalizzazione sullo stesso dato, cioè 4 test — con Bonferroni
p = 0,069, fuori dal 5%. Il costo pratico è alto: 93 coppie su 1225 contengono 18 dei 136 confini,
cioè **recall 13% a precisione 0,19**.

🔵 **Se si vuole insistere sull'audio, il candidato è il silenzio, non l'identità del parlante**:
è l'unica categoria che sopravanza la prevalenza, ed è misurabile **senza diarizzazione** — basta
il VAD che l'ASR usa già. 7 confini su 12 cadono lì.

### 5.10 · La stima di k non funziona

`estimate_scenes_count` (gomito dei valori singolari) contro il numero vero di scene per video:
media **7,2** (HSV) e 10,0 (SigLIP) contro **12,6** reale, e **non segue il video** (GT 22 → stima
5; GT 5 → 7). Chi usa `--scenes` sul serio deve passare `--n-scenes`.

⛔ **`--scenes` resta fuori da `--all`.** Non per il costo (una decodifica in più, 47 s su un film
di 2 h, niente accanto ai 45 min di ASR+VLM): è che `--all` non può passare `--n-scenes`, e senza
quello la stima sbaglia di ~40%. Sarebbe spedire scene note-sbagliate a chiunque scriva `--all`.
Rientra quando la stima di k funziona, o quando la UI le rende ispezionabili.

### 5.11 · Costi e bug trovati dal banco

**Su *Rogue One*** (3204 shot, 192 701 frame): decode 47 s · firme+distanze 2 s · DP 17 s.

⛔ **Il risparmio VLM non esiste.** Il piano vendeva la Fase 1 come *«l'unico vero moltiplicatore
sul costo VLM»*, ma quel moltiplicatore veniva dal **non** descrivere più i singoli shot. Se gli
shot restano un'unità del catalogo con la sua descrizione, le chiamate restano. Su *Anna*: solo
shot 34 min · solo scene ~11 min · **entrambi 45 min (+32%)**. **La Fase 1 non è
un'ottimizzazione, è una feature**: si giudica su navigabilità e ricerca.

🐛 **Bug trovato dal banco, già in produzione: `sample_frames` campionava fuori dallo shot.**
`_timestamps` rientrava di `min(0,15·dur, 0,3)`, che su uno shot da 5 frame a 25 fps vale
**0,03 s — meno di un frame**. `end_time` è esclusivo, quindi l'ultimo istante cadeva oltre il PTS
dell'ultimo frame: ffmpeg, che con `-ss` prende il primo frame *a partire da* t, tornava **il primo
frame dello shot successivo** — o niente, a fine file. Colpiva `faces` e `vlm`, non solo il
grouping: **2,2% degli shot di *Rogue One*** (71 su 3204), 0% su *Anna*. Corretto col tetto
`end − 1/fps`, `fps` propagato dai tre chiamanti.

🔴 **Resta aperto, ed è l'unica cosa che rende le scene utili: la UI a tre livelli.** `scenes` nel
manifest non serve a nessuno finché la galleria non lo mostra.

---

## 6 · ASR

### 6.1 · Il bug che distruggeva metà del parlato

Su *Anna*, 78 shot su 238 contenevano soltanto «Grazie» / «Grazie a tutti», spesso in loop: 77
minuti di film con dialogo fabbricato. Era prevedibile — il restauro 2011 ha *volutamente
conservato* fruscio, interferenze e ronzio del magnetico 16mm, cioè il substrato su cui Whisper
allucina.

**La diagnosi iniziale era incompleta, e la realtà era peggiore.** Non «Whisper riempie il
silenzio», ma un **runaway loop di `condition_on_previous_text`** che, sull'intero film trascritto
in un'unica chiamata, si auto-alimenta e **sovrascrive il parlato reale**. Ri-trascrivendo il
cluster shot 38-48, **tutti e 7 gli shot contenevano dialogo reale** (un monologo su carcere e
politica). Ecco perché il loop **non** si riproduce su una fetta isolata: niente contesto accumulato.

**Ri-collaudo sull'intero film** (12 thread, 41 min):

| | prima | dopo |
|---|---|---|
| shot interamente allucinati | 76 | **1** |
| shot con dialogo | 238 | **266** |
| parole di dialogo | 11 170 | **21 640 (+10 470)** |

**Il loop stava sopprimendo circa metà del parlato del film.**

Fix: `condition_on_previous_text=False` + `is_hallucination` (blacklist, prefisso «sottotitoli…»,
loop di n-gramma ripetuto ≥3×). Gli altri knob (VAD più aggressivo, `no_speech_threshold`,
`compression_ratio_threshold`) lasciati ai default: **su audio degradato alzare le soglie rischia
di tagliare dialogo vero**.

### 6.2 · Il bug della lingua — trovato validando il chunking

Il ramo `vad=True` rilevava la lingua su `wm.detect_language(audio)`, cioè sull'audio **grezzo**.
I primi 30 s di *Anna* sono un cartello muto:

| | lingua | confidenza |
|---|---|---|
| audio grezzo (bug) | `en` | **0,62** — tirava a indovinare |
| `speech_head` (fix) | `it` | **0,99** |

Il run completo col bug aveva prodotto 3375 segmenti **tutti in inglese**
(*«because I'm not an alphabet, I'm not even a creditor»*). Fix: `speech_head(audio, windows)`
concatena i primi 30 s di *parlato* dalle finestre VAD e rileva su quelli.

**È il tipo di difetto che solo la validazione sul film intero trova**: avrebbe corrotto in
silenzio ogni catalogo di film non inglese che non apre parlando.

### 6.3 · Il chunking VAD, e perché WhisperX si chiude

| | parole | tempo (180 s) | loop |
|---|---|---|---|
| baseline (file intero) | 455 | 31,1 s | 0 |
| **chunked (finestre VAD)** | **488** | 36,7 s | 0 |
| WhisperX | 487 | 49,9 s | 0 |

**Il vantaggio di WhisperX è il *chunking*, non il modello.** Il chunking in casa recupera per
intero il divario (488 contro 487) a **+18%** di tempo invece del +45%, ed è **26% più veloce**.
⛔ WhisperX chiuso: un venv parallelo da 1,3 GB con `torch 2.8`/`transformers 4.57` incompatibili,
per un vantaggio che sappiamo riprodurre.

**`speech align`** (forced alignment nativo MLX): 487/487 parole in 3,38 s, scarto mediano 0,24 s
rispetto a WhisperX. ⚠️ Il **21% delle parole ha durata nulla** e 5 finiscono *oltre* la durata
dell'audio: basta per assegnare le parole agli shot, non per una durata affidabile.

⛔ **Parakeet v3** non adottato: 6,32% WER contro 7,44%, ma 25 lingue contro 99 e il margine è su
parlato *pulito*, non su audio cinematografico degradato.

### 6.4 · Aperto sull'ASR

- 🔴 **Run ASR completo su *Anna* a macchina libera** — l'unica cosa in stato **indeterminato**. I
  due tentativi sono stati annullati (bug lingua + macchina contesa da una videochiamata, quindi
  anche i 60,7 min di parete non valgono come confronto coi 41 di baseline).
- 🔵 **`word_timestamps=True`** già in faster-whisper (default `False`): da misurare **prima** di
  cablare `speech align`. Se regge, chiude il punto con un flag.
- 🔵 **`hallucination_silence_threshold`** mai provato — parametro dedicato di faster-whisper.
- 🔵 **`speech denoise`/`restore`** mai provati. È l'intervento più diretto sulla causa: ripulire
  l'audio **a monte** dell'ASR.
- 🔵 **`MAX_WINDOW_S=30` e `min_silence_duration_ms=500`** scelti, non ottimizzati. Il prototipo
  con finestre fino a 49 s dava lo stesso risultato: il valore migliore sta in un intervallo.

---

## 7 · Diarizzazione

✅ **Spedito**: `--diarize` → `transcription/diarize.py`, campo `speakers` per shot, parlanti nel
dettaglio della UI. Backend `speech` (Swift, Homebrew, Apache-2.0): **binario esterno, non una
dipendenza Python**, non tocca il venv e non vuole token HuggingFace. Stesso schema di ffmpeg.

**Indipendente da `--asr`**: dice *chi* parla, non cosa. `--all` non la include finché il linking
speaker↔volto non è misurato.

### 7.1 · L'engine è `pyannote`, e il tetto di Sortformer è reale

Stesso audio (*Rogue One*, 600 s, mono 16 kHz), tre engine dello stesso binario:

| engine | speaker | segmenti | tempo | stimato su 2h14 |
|---|---|---|---|---|
| `sortformer` | **4 esatti** | 76 | 5,4 s | ~72 s |
| **`pyannote`** | **6** | 92 | 11,0 s | **~2,5 min** |
| `community1` | 6 | 115 | 41,0 s | ~9 min |

**Non dice chi ha ragione** — non c'è ground truth, e con 4 dei 6 parlanti sotto i 10 s di parlato
una parte è certamente rumore. Dice che sortformer si ferma a **4 esatti** dove due engine
indipendenti concordano su 6: è il tetto architetturale sospettato, non una coincidenza. Su un
film corale conta.

E **il motivo per cui pyannote era stato scartato non si applica**: «modelli gated» vale per la
libreria Python, non per `speech`, che li serve senza token. `community1` a 9 min non compra nulla
in più.

### 7.2 · Gotcha e aperto

- ⚠️ **`speech diarize --json` scrive i log di avanzamento su stdout, davanti al JSON.** Il parse
  va tagliato alla prima `{`, o muore sulla prima riga.
- **`assign_speakers` assegna per sovrapposizione, non per punto medio** — a differenza di
  `align.assign_dialogue`. Un turno di parola attraversa gli stacchi (campo/controcampo), quindi
  finisce in **tutti** gli shot che tocca.
- 🔵 **`speech embed-speaker`** — gallery vocale per personaggio, linking voce↔volto più solido che
  passare per i nomi nel dialogo.
- ⚠️ **Il banco va deciso prima del linking, non dopo.** BBC ha un narratore solo; su RAI due video
  su dieci hanno il 99-100% del parlato da un solo speaker. Serve materiale **dialogato con GT di
  scena** — che in casa non c'è: MovieNet-SSeg ha i confini ma non l'audio. È la stessa carenza
  che blocca il linking voce↔volto.
- **Sui nomi dal dialogo**: dei 196 candidati "nome proprio" su *Anna*, la maggioranza sono
  toponimi (Africa, Roma, Germania), falsi positivi grammaticali (Non, Come, Perché) o **persone
  citate ma assenti** (`Valpreda` compare 4 volte e non è nel film). I nomi plausibilmente presenti
  sono pochi e rari: Anna (7 shot su 373), Roland (5), Vincenzo (4). Il segnale è sottile:
  scrivere il nome come **suggerimento con confidenza** (`name_hint` + score), **non**
  sovrascrivere `Personaggio N`.

---

## 8 · VLM

### 8.1 · L'ancora b/n — implementata, misurata inutile, rimossa

35 shot in b/n congelati, stessi frame, greedy, unica variabile il flag:

| | colori su b/n | dichiara b/n da sé | parole medie |
|---|---|---|---|
| con ancora | **0/35** | 26/35 | 45,3 |
| senza ancora | **0/35** | 23/35 | 46,8 |

Su alcuni shot le descrizioni coincidono parola per parola. **Era una cura per Qwen2.5-VL-3B-4bit;
uscendo da Qwen2.5 la malattia è sparita.**

**E la giustificazione per tenerla era falsa**: si teneva come rete per lo **shot 0**, ma quel
cartello è testo chiaro su fondo e `_is_grayscale` lo classificava *a colori* — l'ancora non si
attivava mai proprio sull'unico caso per cui la si teneva.

### 8.2 · A/B fra taglie → `Qwen3-VL-8B-Instruct-4bit`

36 shot stratificati su tutto il film (sei celle da sei: corto/medio/lungo × con dialogo/muto,
seed fisso), frame estratti **una volta** con `sample_frames` di produzione e riusati identici,
greedy, un processo per modello:

| | s/shot | peak RAM | colori su b/n | deriva dial. | meta-rif. | troncate |
|---|---|---|---|---|---|---|
| 4B-8bit | **4,42 s** | **6,21 GB** | 0/35 | 6,2% | **7/36** | **3/36** |
| **8B-4bit** | 5,50 s (+24%) | 6,75 GB (+9%) | 0/35 | **1,4%** | **0/36** | **0/36** |
| 8B-8bit | 8,83 s (+100%) | 10,85 GB (+75%) | 0/35 | 2,9% | 2/36 | 0/36 |

**Quello che separa 4B e 8B è la fabbricazione, e si vede sui fotogrammi.** Shot 3 è un cartello di
testo sul restauro: il 4B descrive *«un uomo in piedi, vestito con un abito formale, la testa
leggermente inclinata…»* — sessanta parole inventate su un'inquadratura senza persone; entrambi
gli 8B leggono il testo. Shot 191: il 4B vede *«una donna che parla al telefono»* (nessun telefono
nell'inquadratura).

**Due conclusioni del giro piccolo (8 shot), corrette dal campione ampio:** il nome «Emma» **non
era un'allucinazione** (è nel dialogo ASR); e la **deriva narrativa non cresce con la taglia** — il
massimo è del 4B. L'inferenza opposta era sbagliata.

Altre scelte: **`temperature=0`** (per un catalogo la riproducibilità vale più della varietà, e
tutti i confronti fra modelli erano già in greedy); il dialogo marcato **«solo contesto»** nel
prompt con «non ripeterlo né parafrasarlo».

### 8.3 · Aperto sul VLM

- 🔵 **Cartelli non sono scene** — shot di solo testo (avvisi, note di restauro) descritti come
  inquadrature. Un catalogo dovrebbe marcarli *non-scena*. Il segnale gratis (`_is_grayscale`) è
  stato rimosso: il rilevatore va riscritto per quello che è, un rilevatore di cartelli.
- 🔵 **`max_tokens=128`** arbitrario: non morde con l'8B-4bit (conciso), morderebbe con un modello
  verboso — troncava 3 descrizioni su 36 col 4B.
- 🔵 **Deriva narrativa nel prompt**: la marcatura «dialogo = solo contesto» è ragionata, **non
  misurata**.

---

## 9 · Catalogo, UI, correzione manuale

### 9.1 · L'identità di uno shot è `start_frame`, non `index`

Il taglio manuale sposta di uno **tutti** gli indici a valle. Due punti del codice usavano
l'indice come identità:

**`merge_prior`.** Stesso dato, due accoppiamenti, dopo un taglio a 50:

```
per index      : ['una nave da guerra', 'un pianeta desertico', None]   ← scivolato
per start_frame: ['una nave da guerra', None, 'un pianeta desertico']
```

Con `index` la descrizione finisce su un pezzo di film che non descrive, **in silenzio**. Con
`start_frame` il confine spostato non recupera, **ed è la scelta giusta**: un campo assegnato male
è peggio di uno perso, perché non si vede.

**`extract_thumbs`.** I file si chiamavano `thumbs/{index:06d}.jpg`, e con l'idempotenza
(`if not path.exists()`) una miniatura sbagliata **non si sarebbe rigenerata mai**.

> ⛔ **Affermazione smentita nella stessa sessione.** Era stato dichiarato come limite noto che
> «`thumb` e `clip` li rifà il ritaglio». Falso finché le miniature erano numerate per indice: il
> ritaglio le avrebbe saltate tutte.

**Costo**: al primo run i cataloghi esistenti riestraggono tutte le miniature coi nomi nuovi
(*Rogue One*: 3204 file, 18 MB) e le vecchie restano orfane su disco.

⚠️ **E l'indice era sopravvissuto in altri due posti**, trovati solo il 20 agosto rifacendo *Anna*
a soglia nuova: il ramo di resume dei volti in `pipeline.py` e il resume interno di
`caption_manifest`. Entrambi **ridondanti** con `merge_prior`, entrambi cancellati. Dettaglio e
lezione in §3.6 bis.

⚠️ **E l'inizio da solo non bastava (23 set).** Con una soglia diversa lo shot [s, e] diventa
[s, e'] con lo stesso `start_frame`, e `merge_prior` gli dava la descrizione del pezzo vecchio: è
il caso del §3.6 ter (281 shot su 307 di *Anna* con la descrizione della loro prima metà),
evitato allora solo rifacendo tutto da zero. La regola «se il confine si è mosso il recupero non
avviene» valeva per uno solo dei due confini. Ora la chiave è `(start_frame, end_frame)`; fa
eccezione `rivisto`, che riguarda il confine d'apertura e accoppia sul solo inizio.

### 9.2 · `merge_prior` e i campi costosi

`build_manifest` riparte da zero: senza `merge_prior`, un run che non riaccende `--vlm`/`--asr`
sovrascrive descrizioni e dialoghi con `None`. **È già successo**: `clips/Rogue.One/manifest.json`
ha perso 3204 descrizioni e 897 dialoghi (5h16m di calcolo) in un run `--scenes`, recuperati solo
perché esistevano due copie fatte a mano. `CAMPI_COSTOSI = ("description", "dialogue",
"characters", "speakers")`.

**Resume e crash-safety**: `write_manifest` viene chiamata **prima** dello step lungo, e lo step
rilegge ciò che c'è già. Chi aggiunge uno step lungo segue lo stesso schema o un'interruzione
costa l'intero run.

### 9.3 · `--from-manifest` — il ritaglio non è una pipeline nuova

Sostituisce **solo** la sorgente dei confini. Da lì in giù split, miniature, manifest e UI non
sanno la differenza, quindi non c'è un ramo in più da mantenere.

- **`enforce_min_len` non si applica**: la fusione cieca degli shot brevi mangerebbe proprio i
  tagli appena scelti a mano.
- **`merge_prior` legge dal JSON corretto**, non da quello su disco.
- Cast rinominato a mano e scene corrette vengono riportati.
- `_shots_corretti` valida l'ingresso — è l'unico input della pipeline che non viene dal nostro
  codice. Il caso peggiore è il **film sbagliato**, che taglierebbe tutto altrove senza dire niente.

**Verifica sui frame, non sui log** (clip da 250 frame col numero impresso):

| clip | primo frame | atteso |
|---|---|---|
| `scene-001.mp4` | **0** | 0 |
| `scene-002.mp4` | **100** | 100 |
| `scene-003.mp4` | **137** | 137 |

⚠️ **`--split-mode copy` non va bene per i tagli manuali**: gli inizi cadono giusti ma le clip si
allungano di **2 frame** e si sovrappongono. E il banco era facile — keyframe ogni 25 frame; su un
film vero il GOP è molto più lungo. **Se correggi a mano, `reencode` non è opzionale.**

**Scritto qui, non imposto nel codice — per tre settimane (28 ago).** Il default resta `copy`, e
`--from-manifest` non lo cambiava: solo `--max` forzava `reencode`. Chi scriveva
`scene-detector film --from-manifest corretto.json -o out/` — cioè la riga naturale — ritagliava in
`copy`, e ogni confine messo a mano scivolava indietro **all'ultimo keyframe prima**. Un confine
manuale cade *dentro* uno shot, cioè lontano da qualunque keyframe, quindi è il caso peggiore: su
*Anna* (keyframe ogni ~1 s) un secondo, con GOP da 2 s il doppio. Il manifest aveva il frame giusto
e il taglio no, in silenzio.

```python
# cli.py — `copy` qui non è una scelta veloce, è un difetto
if from_manifest and split_mode is SplitMode.copy:
    split_mode = SplitMode.reencode
```

`none` sopravvive (non taglia affatto). Il test è in `tests/test_recut.py`. **La lezione non è sul
keyframe: è che un avviso in un documento non è un guard**, e questo era scritto per esteso proprio
qui sopra.

### 9.4 · Il taglio a livello shot — l'unità è il frame

Le scene avevano già `unisci`/`dividi`, ma lì l'unità è **lo shot**. Per gli shot l'unità è il
**frame**, e va letta dal player:

```js
function frameBase() { const sh = shots[cur]; return !FILM && sh && sh.clip ? sh.start_frame : 0; }
function frameNow() { return frameBase() + Math.floor($('player').currentTime * DATA.fps); }
function goToFrame(f) { $('player').currentTime = (f - frameBase() + 0.5) / DATA.fps; }
```

- **`frameBase` non è un dettaglio**: con le clip su disco `currentTime` è relativo alla clip, col
  film intero è assoluto. Sbagliarlo taglia nel posto sbagliato **solo su metà dei cataloghi**.
- **Mezzo frame dentro** nel seek, così il `floor` ridà esattamente `f`.
- Niente `requestVideoFrameCallback`: `currentTime` dopo un `seeked` è già il frame mostrato.

**Il ramo della clip è rimasto, ma non lo prende più nessuno (28 ago).** `pipeline.run` scrive
`video_src` **sempre**, anche quando taglia, e la UI riproduce il film pure quando le clip ci sono:
così `frameBase` vale 0 e il conto è esatto per costruzione, invece di dipendere da dove l'encoder
ha messo i keyframe. Il ramo con `sh.clip` serve solo ai cataloghi vecchi, il cui manifest quel
campo non ce l'ha. Costo misurato: il player carica il film intero — su *Anna* 8,4 GB con il `moov`
in coda, **~20 s** prima dei metadati, poi i seek sono immediati. Selezionare uno shot ora avvia la
riproduzione, come già faceva `--split-mode none`.

> ⚠️ **La diagnosi di partenza era sbagliata, e vale più della cura.** Cercavo l'origine di un taglio
> che cadeva 1-2 s più in là, e avevo misurato che le clip `copy` durano 2-4 frame più del dovuto:
> ne avevo dedotto che partissero prima del confine, e che `frameBase` contasse su un'origine
> spostata. **L'extra sta in coda, non in testa.** L'encoder di *Anna* mette un keyframe su quasi
> ogni stacco, quindi le clip partono giuste: su 15 shot campionati l'offset in testa è **0 su 14**,
> e su uno è 2 frame. Il controllo che ha chiuso la questione è un hash 8×8 del fotogramma preso in
> browser: film a 232,800 s e clip a `currentTime 0` danno lo **stesso identico frame**. Il colpevole
> dei 1-2 s era il ritaglio in `copy` (§9.3), non il contatore. La correzione al contatore resta
> perché su un film a GOP fisso, senza keyframe sugli stacchi, l'errore sarebbe stato pieno — ma è
> un'altra cosa da quella che stavo cercando.

### 9.4 bis · I comandi di riproduzione (28 ago)

Tre comandi nella barra sotto il player, tutti verificati in browser su un banco corto (uno shot
di 4 s ritagliato in tre) invece che sul film intero:

- **`⏹ stop a fine shot`**, un toggle **spento di default**. Acceso, la riproduzione si ferma
  sull'**ultimo frame** dello shot: il `timeupdate` arriva fino a 250 ms oltre il confine, quindi si
  torna indietro di mezzo frame. Misurato: shot 0–32, pausa a 1,300 s, `frameNow 32`.
- **`⏪ 5s` / `5s ⏩`**, che **attraversano i confini** — la testina segue la timeline, non lo shot.
  Il `seeked` disarma `stopAt` appena si finisce fuori, quindi non ripausa a sorpresa.
- **velocità** 0,25× / 0,5× / 1× / 2×, con `preservesPitch` e **`defaultPlaybackRate`**: caricare
  una src nuova (i cataloghi con le clip) rimette `playbackRate` a quel valore, e senza la velocità
  si azzererebbe a ogni shot.

Due cose che non erano ovvie:

1. **Il default non era quello che sembrava.** «Riproduzione continua» era il comportamento
   descritto, ma `seekTo` armava `stopAt` a *ogni* selezione: il player si fermava sempre a fine
   shot. Ora `stopAt` lo arma solo il toggle — e `playScene`, che passa `ferma = true` esplicito,
   perché suonare una scena è un'altra cosa.
2. **Disarmare prima di riposizionare.** Tornando sull'ultimo frame con `stopAt` ancora armato, il
   play successivo ripausa dopo mezzo frame: da fuori il video sembra piantato.

**Il contrasto si misura sul tema che non stai guardando** (già §2, ma è ricascato qui): lo stato
acceso del toggle è riempito di `#8ab4ff`, e colorarne anche il bordo lo portava a **1,9:1** sul
tema chiaro, sotto il 3:1 che serve a un elemento grafico. Bordo lasciato `#555`, che fa 6,9:1.
Sul tema scuro il problema non si vedeva.

**Perché `✂ taglia qui` a volte è spento**: selezionando uno shot la testina sta sul suo **primo**
frame (tagliare lì non spezza niente); lasciando scorrere, la riproduzione si ferma a `end_time`,
che è **un frame oltre** l'ultimo. Il guard era giusto, mancava il perché — ora accanto al numero
c'è il range dello shot.

### 9.5 · Il player che «riparte da zero» — due colpevoli su tre, ed era il server

**La causa principale non era nel codice.** Il catalogo era servito con `python -m http.server`,
che **ignora le richieste `Range`**: risponde `200 OK` invece di `206 Partial Content`. Senza
`Range` il browser non può cercare: ogni `currentTime = x` ricade su ciò che ha bufferizzato dal
byte 0. WEBrick regge il `Range` ma **muore sugli abort** che il browser manda a ogni seek
(`PIPELINE_ERROR_READ: FFmpegDemuxer: data source error`). Risolto con `ThreadingHTTPServer` +
`Range`, un thread per richiesta.

> ⚠️ **Per l'uso normale non serve nessun server**: doppio click su `index.html` e il browser legge
> il film da disco. La sessione del 24 luglio diceva il contrario («`file://` non riproduce video
> grandi»): con `--split-mode none` e i path relativi corretti funziona. Il server serve solo a
> pilotare il browser da un'estensione.

**Due bug veri, questi sì nel codice.** `stopAt` restava armato: play a fine shot non ripartiva (si
è fermi **su** `stopAt`, il primo `timeupdate` ripausa) e un seek manuale causava pausa immediata.
`stopAt` vincola *la riproduzione avviata da noi*, non il player: si guarda dove sta la testina,
niente flag da tenere in sincrono.

### 9.6 · Clip orfane e layout del catalogo

Un run che produce **meno** shot di prima lasciava su disco le clip in eccesso: nome legittimo,
contenuto ormai duplicato, nessun manifest che le citi. Ora vengono rinominate `.orfano` — non
cancellate, e il suffisso le toglie dal glob. Il fix sta in `splitter.split` e **non** nel ramo
`--from-manifest`: il problema è di ogni run che riduce il numero di shot.

> **Non `sorted(...)[len(scenes):]`**, che è la versione ovvia e sbagliata. Il template è `{:03d}`
> ma sopra i 999 shot i nomi passano a 4 cifre (*Rogue One* ne ha 3204), e in ordine lessicografico
> `scene-1000.mp4` viene **prima** di `scene-999.mp4`.

```
clips/Film/
├── manifest.json        # il backbone: ogni step lo riempie e lo riscrive
├── index.html           # UI autonoma, i path dentro sono relativi a QUI
├── clip/                # scene-001.mp4, … (assente con --split-mode none)
├── thumbs/ · faces/
└── logs/run-<ts>/
```

La cartella passata a `split` e il `clip_template` di `build_manifest` **devono combaciare**:
stanno a tre righe di distanza in `pipeline.py`, ed è l'unico posto dove il legame è visibile.

### 9.7 · `--split-mode none` e i media fragments

Il piano proponeva di **smettere** di tagliare le clip. ⛔ **Respinto come default**: le clip su
disco restano la normalità. Implementato come **modalità opzionale**: salta il taglio, mette
`clip: null` nel manifest e aggiunge `video_src` (path relativo dal catalogo al film).

⚠️ **La UI carica il film una volta e sposta `currentTime`**, non riassegna `player.src` col
frammento `#t=`: riassegnare è inaffidabile su un file da 2,7 GB (ricarica tutto, e se cambia solo
il frammento il browser non ricarica → resta fermo).

### 9.9 · La UI diventa uno strumento di lavoro (28 ago)

Fin qui il catalogo era una pagina da guardare con due correzioni possibili. In una sessione è
diventato il posto dove il lavoro si fa: quattro viste (`lista`, `⚑ rivedi`, `⊞ scheda`, `? aiuto`),
una variabile sola `vista` e non tre booleani — due booleani si accendono insieme e poi bisogna
decidere chi vince.

**Coda di revisione per confidenza.** Il detector sa già dove ha dubitato: la coda mette in fila
gli shot con `confidence` sotto 0,50 e tutte le graduali, dal più incerto, e si smaltisce con
`↑↓` e `V` (che scrive `rivisto`, ora in `CAMPI_COSTOSI`: non costa GPU, costa ore di persona).

> ⛔ **Smentito il 23 set.** Qui c'era scritto: «41 confini sotto 0,50, 48 graduali, **41 in
> comune** — non è un caso, una dissolvenza spalma la probabilità e il picco resta basso». Il
> picco non restava basso: `boundary_confidences` leggeva `probs[s-1]`, che con `runs_to_ranges`
> è l'**ultimo** frame della corsa, cioè quello appena sopra la soglia per costruzione. Sulle 48
> graduali: confidenza mediana **0,10**, picco mediano **0,675**, picco sotto 0,5 in **0** casi —
> `--min-peak 0.5` le aveva già tolte tutte. Quelle 41 erano la popolazione che nei controlli di
> `annota_deboli` era **12/12 stacchi veri**, non quella dello 0/24. Su *Rogue One* 510 graduali
> su 515 finivano sotto 0,5, col picco sotto 0,5 solo in 284: la coda ordinava per **larghezza**,
> non per dubbio. Ora la confidenza è il picco della corsa, la stessa grandezza di `--min-peak`.
> La conclusione pratica regge per un altro motivo: su *Anna* la coda sono comunque le 48
> graduali, perché entrano tutte per regola — ma con zero confini «incerti».

**Scheda del film.** ASL 41,8 s, mediana 19,9 s, e l'istogramma dice che non è una media che
nasconde: **130 shot su 307 durano più di 32 s**. Più il ritmo del montaggio (una barra per shot,
alta quanto dura, cliccabile) e i minuti in scena per personaggio. Nessun dato nuovo: è tutto già
nel manifest, non lo mostrava nessuno.

**Salvataggio nel browser, e la sua impronta.** Ogni modifica finisce in `localStorage` 400 ms
dopo l'ultimo tasto — non a intervalli. La chiave porta un'**impronta** del catalogo
(`n_shots/fps/start_frame del primo/dell'ultimo`): se rigeneri e i confini si spostano, il
ripescaggio non avviene, perché parlerebbe di shot che non esistono più. È la stessa regola di
`merge_prior`, applicata al browser. L'annulla tiene venti istantanee di `{shots, scenes, cast}`.

⛔ **Corretto il 23 set: la copia intera nascondeva i run successivi.** Un `--vlm` sugli stessi
confini non cambiava l'impronta, quindi riaprendo la pagina la copia nel browser — senza
descrizioni — sostituiva in blocco gli shot nuovi; un export seguito da `--from-manifest` le
perdeva davvero, cioè il danno che `CAMPI_COSTOSI` esiste per evitare. Ora si salvano le
**differenze** dal manifest arrivato da disco (confini, testi, `rivisto`, nomi, fusioni) e al
ripescaggio tornano sopra il manifest nuovo. L'impronta sono i range del detector; se il cast è
stato rifatto da capo, rinomine e personaggi per shot non tornano, perché gli id vogliono dire
un'altra cosa. I salvataggi nel formato vecchio si ripescano ancora una volta, come prima.

**Fusione dei personaggi.** Il clustering sbaglia in un verso solo che si possa correggere a mano:
**spezza** una persona in due gruppi. Due clic, `⇄` sulla faccia che sparisce e poi sulla faccia
che resta. Il conteggio va **rifatto sui dati**, non sommato: su una coppia che compare insieme in
10 shot, 16 + 43 fa 49, non 59.

**EDL e SRT.** I confini sono già al fotogramma: l'EDL è un cambio di notazione. `end_frame` è
inclusivo e il CMX3600 vuole l'estremo escluso, quindi `+1` — come ovunque.

#### Le trappole di layout, tutte trovate misurando e nessuna a occhio

| cosa | perché |
|---|---|
| `[hidden]` non nascondeva `<main>` | `main { display:grid }` è una regola d'**autore** e batte il `[hidden]` dell'**agente**. Il JS diceva `mainNascosto: true` mentre lo schermo mostrava la lista |
| la pagina sforava di lato a 390 px | `1fr` vale `minmax(auto,1fr)`, e quel minimo è il *contenuto minimo*: la colonna della lista non scendeva sotto **519 px**. Serve `minmax(0,1fr)` |
| i bottoni di dialogo e descrizione schiacciati a una fetta di pixel | `#detail` è una colonna flex e li stringeva; l'`overflow:hidden` dei puntini tagliava il testo invece di lasciarlo traboccare. `#detail > * { flex-shrink:0 }` — la colonna scorre già |
| il menu d'esportazione spariva sotto la timeline | la testata è `position:sticky`, cioè un **contesto d'impilamento**: lo `z-index:5` del menu si confronta dentro la testata. A pari z-index vinceva la timeline, che viene dopo |
| il chevron delle scene «rotto» | chiudeva davvero, ma `select()` faceva `open.add(si)` a **ogni** chiamata e la prima freccia rispalancava. Aprire ha senso quando si **cambia** scena, non muovendosi dentro |

E i numeri magici sono spariti: il corpo era alto `calc(100vh - 84px)`, cioè la somma a mano di
testata e timeline — bastava la striscia del cast per sballare. Ora è una colonna flex.

#### La UI parla la lingua del *Fuori campo*

Stessi token, stessi bottoni squadrati, stato acceso = inversione inchiostro/fondo, e i tre
caratteri (Archivo, Newsreader, IBM Plex Mono, SIL OFL) **dentro il file**: un `<link>` a Google
Fonts da `file://` fallisce in silenzio. Sono 268 KB di woff2 in `scene_detector/catalog/font/`,
dichiarati come `package-data`, che diventano ~590 KB di base64 in ogni `index.html`.

> **Il contrasto si misura sul tema che non stai guardando.** I due accenti presi di là stavano a
> 7,8 e 9,4 sullo scuro e a **3,58 e 4,20** sul chiaro, sotto il 4,5 che serve al testo: di là sono
> **fondo** per testo bianco, qui sono **testo** su fondo chiaro. Scuriti a `#287A8A` e `#B05800`,
> tutt'e due a 4,53.

### 9.8 · Aperto sul catalogo

- 🔵 **Miniature vecchie orfane** dopo il rename da `{index}` a `{start_frame}`. Uno script di
  rinomina dal manifest le salverebbe: ~5 righe.
- 🔵 **Il taglio manuale non è tracciato.** Uno shot corretto a mano è indistinguibile da uno del
  detector (`source="manuale"` sta nella `Scene`, non arriva al manifest). Servirebbe un campo per
  misurare il detector **contro** le correzioni — che sarebbe anche il modo più economico di farsi
  un ground truth vero.
- 🔵 **`--faces` dopo un ritaglio** rilegge il cast dal manifest su disco invece che da quello
  corretto: le rinomine fatte nella UI perdono contro la copia più vecchia. Nicchia.
- 🔵 **`clips/Anna/manifest.cleaned.json` e `.pre-asr-fix.json`** citano ancora i path piatti delle
  clip. Istantanee fatte a mano, non toccate.
- 🔵 **Filtro per confidenza nella UI** — il 19% degli shot di *Rogue One* ha confidenza < 0,2 (col picco; il 25% era misurato sulla coda, §9.9). **Una riga di JS.**
- 🟡 **Ricerca sul catalogo.** Caption + transcript + embedding per scena → `index.html` cercabile
  (faiss + SigLIP, entrambi MIT). Rende molto di più **dopo** le scene.

---

## 10 · Infrastruttura

### 10.1 · Fatto

| | |
|---|---|
| **Telemetria** | `core/telemetry.py`: `step()` context manager + `ResourceSampler` (thread psutil, CPU%/RSS medio+picco) + `RunStats` incrementale. Output in `<out>/<film>/logs/run-<ts>/` (`run.log` + `config.json` + `run_stats.json`) con symlink `latest`. `config.json` scritto **all'inizio**, `run_stats.json` a fine di **ogni** step: un run interrotto conserva le metriche degli step conclusi |
| **Package per dominio** | layout piatto → `core/` `io/` `detection/` `segmentation/` `transcription/` `captioning/` `catalog/` `evaluation/`. Orchestrazione estratta da `cli.py` a `pipeline.py` |
| **Galleria multi-film** | `catalog/gallery.py`, statica, zero deps. Scritta automaticamente a fine run; rebuild via `scene-detector-index` |
| **Setup plug-and-play** | `core/weights.py` (registro nome → URL + sha256 + destinazione), `scene-detector-setup`, `install.sh`, extra `all` |
| **Decode-once** | `detect(info)` decodifica da sé, `detect_from_frames(frames, info)` riceve i frame già letti |
| **Resilienza per-shot** | `try/except` per shot nel VLM: uno shot "velenoso" non ferma il batch, e a fine step si logga il conteggio dei falliti |

**La scoperta che ha reso possibile il setup:** entrambi i pesi hanno un mirror pubblico su
HuggingFace, senza auth. `backseollgi/AutoShot` serve `ckpt_0_200_0.pth` **identico byte per
byte**; `MiaoshouAI/transnetv2-pytorch-weights` è una conversione diversa (845 byte in più) ma con
**90/90 tensori uguali**, verificato con `torch.equal`. Il README diceva *«non esiste mirror
diretto, l'unica fonte è Baidu»*, ed era falso. Download completo: **8,6 s**.

### 10.2 · Verificato e scartato

⛔ **Decode-once multi-output ffmpeg — premessa falsa.**
- **Non ci sono 4 decode del film.** La detection è **già** decode-once; faces e VLM **non**
  decodificano il film, fanno estrazione *sparsa* a seek (6 e 3 frame/shot); l'ASR decodifica
  l'**audio**. Un passaggio multi-output a piena risoluzione sarebbe **più lento** per i consumatori
  sparsi.
- **`-hwaccel videotoolbox` è una regressione 4×** sul path 48×27: **1278 f/s** software contro
  **309 f/s** con videotoolbox (**0,24×**). Il readback GPU→CPU per frame supera il decode banale a
  quella risoluzione.

⛔ **VLM server + prefix cache (APC) — non ripaga.** L'APC è prefix-cache a blocchi la cui chiave
**include il contenuto dell'immagine**, quindi fra shot con immagini diverse riusa solo i blocchi
*prima* della prima immagine. Prefill = 741 token: **540 immagine (73%)**, e il prefisso
condivisibile è **15 token (2%)** (Qwen mette le immagini *prima* dell'istruzione). E `generate` è
dominato dal **decode dell'output**, che l'APC non tocca. Best case ~2-5% per shot. Il modello lo
teniamo già residente: il server aggiunge solo IPC.

⛔ **Il path `--low-mem`** — ~120 righe per evitare 1,2 GB di picco, e in ensemble **raddoppiava il
decode** invece di dimezzare la RAM. I frame stanno interi in RAM: ~1,25 GB per un film di 2 h a
48×27. È una scelta.

### 10.3 · Audit di over-engineering (23 lug)

I 17 findings con file e riga stanno in [`Audit (07-23).md`](../Audit%20(07-23).md), che resta
separato perché è un referto, non un verbale. Qui il consuntivo: 4738 → 4347 righe, 54 → 49 file. **Nessuna regressione**: manifest, `index.html` e metriche
identici al pre-refactor su 5 video, probs bit-per-bit.

Applicati: via `--low-mem`; i due detector unificati in una classe parametrica; i due predictor in
`_WindowedPredictor` con tre hook; via `base.py` (un `Protocol` `@runtime_checkable` che non
passava mai per un `isinstance`) e `factory.py`; via `evaluate`/`f1_curve`/`read_scenes_txt` (zero
chiamanti in produzione, tenuti vivi solo dai test — **il sintomo classico del codice morto
testato**); `cluster_within_shot` fuso in `cluster_faces`; `_prf` condiviso invece di P/R/F1
scritto quattro volte; `pipeline.run` legge `cfg.x` invece di spacchettare 20 campi; via i wrapper
`main_*` (gli oggetti Typer sono callable); `centroids_of` ≡ `average_embeddings`; via
`adaptive`/`pyscd_threshold`/`save_every`/`min_shot_frames`; via le riesportazioni di `__init__.py`;
`html.escape` invece dell'escaping a mano.

**Non applicati:** rimuovere la dep `scenedetect` (PySceneDetect resta come baseline documentata) ·
toccare il codice vendored (rischio mismatch `state_dict` non giustificato dal guadagno).

**Fuori scope ma trovato:** `tqdm` importato in 6 moduli e non dichiarato in `pyproject.toml` —
l'installazione base si rompeva al primo decode.

### 10.4 · Debito residuo

- `Config.agreement_tol` — **zero lettori** nel package (residuo dell'ensemble).
- `confidence.reconcile` — **zero chiamanti**; ripristinato col commit AutoShot ma non ricablato.
- `DetectorKind.autoshot` è in `build_detector` ma `--autoshot-weights` non esiste in `cli.py`:
  `-d autoshot` fallisce sempre con «pesi mancanti».
- `probs_to_ranges` e `siglip_signatures` — vivi solo nei test / zero chiamanti.
- `adapt.py` cita `faces.teacher_clusters`, che si chiama **`split_by_reliability`**.
- ✅ Chiusi il 20 ago: i due resume accoppiati per `index` (§3.6 bis).
- 🔵 **Frame condivisi faces+vlm** — oggi campionano gli stessi shot in modo indipendente (6
  seek@640 + 3 seek@512). Vale ~2-3 min/film. È l'unica parte del decode-once sopravvissuta.
- 🔵 **Setup plug-and-play, la coda.** I 3 modelli grandi (`--models`) non sono collaudati da zero
  su macchina pulita, e nessuno ha hash verificato — si fidano del proprio hub.

### 10.5 · Gotcha operativi

- **`python -m http.server` non implementa `Range`**: serve l'`index.html` ma il video **non si può
  cercare**. Sembra un bug della UI e non lo è.
- **`tqdm` in un file di log** scrive una riga per aggiornamento e seppellisce l'output utile:
  `progress=False` quando non sei su un terminale.
- **Job in background**: `nohup … &` non basta, lo shell li sospende se toccano il tty
  (`suspended (tty output)`). Servono `< /dev/null` e `disown`.
- **Overnight**: `caffeinate -is -t 28800 &`, o il Mac va in sleep. Non copre la chiusura del coperchio.
- **Non pipare un job di background attraverso `grep`**: bufferizza e il file resta a 0 byte finché
  il processo non chiude.
- **zsh interattiva: `#` non è un commento.** Un comando incollato con `# nota` fa espandere `~1`
  come stack di directory.
- **Un pickle da un mirror di terze parti è codice eseguibile**: `_SafeUnpickler` in
  `evaluation/shot_dataset.py` è lì per questo.
- **`np.savez_compressed` appende `.npz`** a qualunque nome che non lo abbia già: un temporaneo
  `.part` diventa `.part.npz` e il `replace` dopo fallisce.
- **`nb_frames` è un metadato del container e sa mentire**: su un file tagliato con `-c copy` conta
  i pacchetti del GOP originale. Si prende il **minimo** fra `nb_frames` e `duration × fps`.
- **`drawtext` non c'è in ogni build di ffmpeg**: i frame numerati si generano con cv2.
- **`sorted()` su nomi con numeri a larghezza variabile** ordina alfabeticamente, non numericamente.
- **Un `seeked` che non arriva mai** non è la logica che non funziona: è la sorgente morta.
  Controllare `player.error` prima di sospettare il proprio codice.
- **L'estensione del browser non naviga su `file://`.**
- **OmniShotCut vive in un venv separato** (`prove/.venv_omni`), che non ha `scene_detector`: da qui
  i due passi `--infer` e valutazione.

---

## 11 · Ecosistema e licenze

### 11.1 · I repo, con verdetto

**Shot detection**

| Repo | ⭐ | Licenza | Verdetto |
|---|---|---|---|
| [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) | 5 040 | BSD-3 | **in uso** (baseline) |
| [TransNetV2](https://github.com/soCzech/TransNetV2) | 995 | MIT | **in uso** (primario), non più aggiornato |
| [AutoShot](https://github.com/wentaozhu/AutoShot) | 246 | MIT | **solo banco** (§3.7) |
| [OmniShotCut](https://github.com/UVA-Computer-Vision-Lab/OmniShotCut) | — | MIT (anche i pesi) | **adottabile**, rimandato a un film con dissolvenze |

**Scene grouping**

| Repo | Licenza | Verdetto |
|---|---|---|
| [BaSSL](https://github.com/kakaobrain/bassl) | Apache-2.0 | ⛔ i pesi sono pre-training, va finetunato |
| [SceneSeg / LGSS](https://github.com/AnyiRao/SceneSeg) | **nessuna** | pesi + tool; usabile in locale, **non vendorabile** |
| [SCRL](https://github.com/TencentYoutuResearch/SceneSegmentation-SCRL) | NOASSERTION | *riferimento* |
| [TranS4mer](https://github.com/md-mohaiminul/TranS4mer) | Apache-2.0 | ⛔ *Pre-trained Models: TODO* |
| Scene-VLM | — | ⛔ né codice né pesi |

**ASR / diarizzazione**

| Repo | Licenza | Verdetto |
|---|---|---|
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | MIT | **in uso** (+ chunking VAD nostro) |
| [WhisperX](https://github.com/m-bain/whisperX) | BSD-2 | ⛔ il vantaggio è il chunking, non il modello |
| [speech-swift](https://github.com/soniqo/speech-swift) | Apache-2.0 | **adottato** — engine `pyannote` |
| [pyannote-audio](https://github.com/pyannote/pyannote-audio) | MIT | il «gated» **non vale dentro `speech`** |

**Volti**

| Repo | Licenza | Verdetto |
|---|---|---|
| [InsightFace](https://github.com/deepinsight/insightface) | codice MIT, **model package separato** | **in uso** |
| [Video_Person_Clustering](https://github.com/Andrew-Brown1/Video_Person_Clustering) | MIT | **dataset + metriche** (VPCD): 35 396 face-track su 23 h |
| [ByteTrack](https://github.com/FoundationVision/ByteTrack) | MIT | ⛔ non applicabile con frame sparsi |
| [BallClustering](https://github.com/makarandtapaswi/BallClustering_ICCV2019) | **nessuna** | risolve il problema esatto (n. cluster ignoto) ma non è riusabile |

**VLM / ricerca**: [mlx-vlm](https://github.com/Blaizzy/mlx-vlm) (MIT, in uso) ·
[faiss](https://github.com/facebookresearch/faiss) (MIT, adottabile) ·
[open_clip](https://github.com/mlfoundations/open_clip) (NOASSERTION) ·
[VideoHighlighter](https://github.com/Aseiel/VideoHighlighter) (**AGPL-3.0**, contagiosa).

### 11.2 · La regola sulle licenze

Tre repo utili **non hanno licenza** (SceneSeg, BallClustering, in parte SCRL/open_clip come
`NOASSERTION`): senza licenza il default è "tutti i diritti riservati", e i ToS di GitHub
concedono solo *view* e *fork*.

**Ma la domanda giusta non è se il repo è libero: è cosa ne facciamo.** Il README di SceneSeg
dichiara l'intento di condivisione, che copre l'uso **locale** (scaricarlo, farlo girare,
valutarlo, tenerlo nella propria pipeline). Non copre la **ridistribuzione**, cioè il vendoring.

> **Regola adottata: codice senza licenza si scarica al setup, non si vendora.** Stesso schema di
> `core/weights.py` per i pesi: il file arriva dalla fonte originale sulla macchina di chi
> installa, noi ridistribuiamo zero.

`detection/models/` vendora TransNetV2 (MIT) e AutoShot (MIT). Il model package `buffalo_l` di
InsightFace è a **licenza separata** (ricerca non commerciale), distinta dal codice MIT — nei
crediti stava accanto a «TransNetV2 (MIT)» come se fosse la stessa cosa.

### 11.3 · Cosa non esiste

Nessuna pipeline locale su Apple Silicon che vada da shot → scene → VLM → ASR → volti → catalogo
navigabile. I pezzi esistono tutti separatamente; l'integrazione su MLX e lo **scene grouping** non
compaiono in nessuno dei progetti trovati.

---

## 12 · Deciso — non si fa

| Cosa | Perché | §|
|---|---|---|
| ⛔ Rimettere **AutoShot in pipeline** | `reconcile` è un'unione, non un veto; sull'ensemble vecchio *aggiungeva* 66 tagli; errori correlati per costruzione | 3.6, 3.7 |
| ⛔ **Decode-once multi-output ffmpeg** | premessa falsa, `hwaccel` è 0,24× sul path 48×27 | 10.2 |
| ⛔ **VLM server + APC** | prefisso cacheable 2%, non ripaga | 10.2 |
| ⛔ **`--low-mem`** | 120 righe per ~1 GB, e in ensemble raddoppiava il decode | 10.2 |
| ⛔ **WhisperX** | il vantaggio è il chunking, non il modello; vuole torch 2.8 | 6.3 |
| ⛔ **Parakeet v3** | margine su parlato pulito, non su audio degradato | 6.3 |
| ⛔ **Ancora b/n nel VLM** | 0/35 con e senza, su Qwen3-VL | 8.1 |
| ⛔ **`min_scene_len` da solo** | +1 punto di F1, non 6; le corse dominano | 3.10 |
| ⛔ **Ibrido ArcFace + SigLIP grezzo** | scambia un cluster sbagliato con tre | 4.8 |
| ⛔ **DINOv2 grezzo sui ritagli** | nessuna soglia funziona | 4.4 |
| ⛔ **Adattatore «stesso shot = stessa identità»** | 8 191 positivi contro 2 676 785 falsi negativi | 4.4 |
| ⛔ **MovieNet per la testa** | +0,004 AUC per 162 GB | 4.6 |
| ⛔ **VLM come battezzatore** | verificatore 5/5, ma i nomi allucinano | 4.9 |
| ⛔ **ByteTrack per i volti** | presuppone video denso, noi campioniamo sparso | 4.1 |
| ⛔ **BaSSL / TranS4mer / Scene-VLM** | vanno addestrati | 5.5 |
| ⛔ **DP penalizzato per la densità** | è k travestito, rapporto ~1,0 dove il vero è 3,0 | 5.8 |
| ⛔ **Novelty per la densità** | pareggia OSG, ma rapporto 0,59-1,12 su 12 combinazioni | 5.8 |
| ⛔ **Il correttivo della punteggiatura in OSG** | 0/7 giudicati cambi di scena, sotto il controllo casuale | 5.6 |
| ⛔ **La voce come segnale di scena** | anti-predice: 0 confini su 44 cambi di parlante | 5.9 |
| ⛔ **`--scenes` dentro `--all`** | `--all` non può passare `--n-scenes` e la stima sbaglia del 40% | 5.10 |
| ⛔ **Rimuovere la dep `scenedetect`** | baseline documentata | 10.3 |
| ⛔ **Toccare il codice vendored** | rischio `state_dict` non giustificato | 10.3 |
| ⛔ **Media fragments come default** | le clip su disco restano la normalità | 9.7 |

---

## 13 · Aperto

**Ora, su *Anna* (il lavoro si basa su quello)**

- ✅ **`--min-peak`** — fatto (§3.6). Catalogo rigenerato con `--threshold 0.05 --min-peak 0.5`.
- 🔴 **La stessa annotazione cieca su *Rogue One*** prima di accendere `--min-peak` altrove: là le
  corse deboli sono 933 e si assume — mai verificato — che siano shot legittimi.
- ✅ **Run ASR completo** — fatto nello stesso run di *Anna*, a macchina libera. Era l'unica cosa
  in stato indeterminato del progetto.

**Detection**

- 🟡 **OmniShotCut in pipeline** — misurato complementare (union: recall 0,215 → 0,534). Dipende
  da: materiale con dissolvenze + `reconcile` riscritta **su range** + una dep nuova in venv
  separato a 128×96.
- 🔵 Etichette di transizione come metadati (arrivano gratis con Omni).
- 🔵 `Sudden_Jump` — scarti da pausa-macchina del Portapak, nessun detector li modella.
- 🔵 **GT boundary manuale** — ~20 boundary annotati darebbero un metro dove oggi si assume che il
  manifest abbia ragione. Il modo più economico: tracciare le correzioni manuali della UI (§9.8).

**Volti** — vedi §4.11: purezza VPCD 🔴 · cast stantio 🔴 · frammentazione 22↔85 🟡 · recall 🔵 ·
provino stabile 🔵.

**Scene**

- 🔴 **Le descrizioni VLM come feature di densità** — sono già nel manifest, gratis. È l'unica
  ipotesi rimasta dopo che DP e novelty hanno fallito nello stesso modo.
- 🔴 **UI a tre livelli** — `scenes` nel manifest non serve a nessuno finché la galleria non lo
  mostra.
- 🔵 Il silenzio (VAD) invece dell'identità del parlante.

**Diarizzazione** — linking speaker↔volto per co-occorrenza 🔴 (⚠️ **il banco va deciso prima**) ·
`speech embed-speaker` 🔵.

**ASR / VLM / catalogo / infra** — vedi §6.4, §8.3, §9.8, §10.4.

---

## 14 · Dove stanno i dati

`.gitignore` esclude `prove/`, `weights/`, `clips/` e `Film/`. `prove/` contiene le baseline di
misura e gli script d'esperimento: **tutto rigenerabile, niente di necessario alla pipeline**. Gli
script **importano il codice di misura l'uno dall'altro** (`tally`, `runs_above`,
`pipeline_transitions` vivono in `runs_ab.py`) invece di riscriverlo, così il protocollo resta
l'unica costante fra un confronto e l'altro.

| script | banco | GT |
|---|---|---|
| `runs_ab.py` · `minlen_ab.py` | test set di SHOT, 50 video | pubblico |
| `detect_ab.py` · `annota_boundary.py` | *Rogue One* | nessuno / annotazione cieca a campione |
| **`annota_deboli.py`** | ***Anna*, corse deboli** | **annotazione cieca con controlli** |
| `xfade_sweep.py` | transizioni generate con `ffmpeg xfade` | esatto per costruzione |
| `rai_ab.py` · `rai_scene_ab.py` · `rai_diar_ab.py` | RAI, 10 video broadcast | confini di scena |
| `clipshots_ab.py` · `omni_ab.py` | ClipShots `only_gradual`, 257 video | graduali **col range** |
| `bbc_scene_ab.py` | BBC Planet Earth, 11 episodi | scene, **5 annotatori** |
| `osg_variants.py` · `lambda_ab.py` · `novelty_ab.py` | RAI + BBC + i due tratti | — |
| `scene_ab.py` · `annota15_ab.py` | *Rogue One*, tratti annotati stacco per stacco | annotazione integrale |
| `faces_cache.py` · `faces_ab.py` · `faces_sheet.py` | cache embedding volti | — |
| `body_ab.py` · `adapt_ab.py` · `transfer_ab.py` · `refine_ab.py` · `probe_ab.py` | ritagli di figura | `labels-661.txt` |
| `appearance_ab.py` | SigLIP sui ritagli | ⚠️ usava `PAD=0,6` (testa e spalle, non figura) |
| `movienet*.py` | MovieNet, 630 film | identità IMDb |
| `vlm_naming.py` · `vlm_purity.py` | *Rogue One* + *Anna* | GT **costruito** |
| `costo_corse.py` · `picco_sweep.py` · `offset_check.py` · `boundary_check.py` | diagnostica | — |

**Cache riusabili** (evitano ore di ricalcolo): `prove/Anna/probs.npy` ·
`prove/Rogue.One/probs_transnet.npz` · `prove/shot-dataset/probs/*.npz` (50 video, 7,5 min di
estrazione) · `prove/faces-Rogue.One/` (8839 volti) · `datasets/movienet/` (hard link).

---

## 15 · Paper di riferimento

Il problema "chi parla e chi è" ha un nome in letteratura: *character-aware subtitling* /
*speaker naming in movies*.

- **[Character-aware audio-visual subtitling in context](https://arxiv.org/pdf/2410.11068)** — Huh
  & Zisserman (VGG Oxford, 2024). ASR + diarizzazione + riconoscimento personaggi + un LLM che
  ragiona sul contesto temporale. **Il design più vicino a quello che serve a noi.**
- **[Character-Centric Understanding of Animated Movies](https://arxiv.org/html/2509.12204)** —
  VGG Oxford, set 2025. DINOv2 su ritagli di corpo + ECAPA-TDNN + SAM2. 81,8 AP contro 45,3 di
  InsightFace.
- **[Face, Body, Voice](https://arxiv.org/pdf/2105.09939)** — Brown, Kalogeiton, Zisserman (ICCV-W
  2021). **VPCD**: dataset e metriche per la purezza dei cluster.
- [Speaker Naming in Movies](https://arxiv.org/pdf/1809.08761) ·
  [Deep Multimodal Speaker Naming](https://arxiv.org/pdf/1507.04831) — i lavori fondativi.
- [ScreenWriter](https://arxiv.org/pdf/2410.19809) — genera sceneggiature da video, nomina i
  personaggi con clustering a grafo.
- [OmniShotCut](https://arxiv.org/abs/2604.24762) (2026) ·
  [TranS4mer](https://arxiv.org/abs/2212.14427) (CVPR 2023).
- **Optimal Sequential Grouping** — Rotman, Porat, Ashour (IBM 2016). Riferimento MIT:
  [ivi-ru/video-scene-detection](https://github.com/ivi-ru/video-scene-detection).
- **Novelty a kernel scacchiera** — Foote (2000). **Change-point penalizzato** — Killick (2012).
- *Introduzione al linguaggio del film* — il manuale da cui vengono le definizioni di scena
  (r. 1591, unità di continuità temporale), montaggio alternato (r. 1583), metodo di copertura
  (r. 1117), punteggiatura (r. 1251).
