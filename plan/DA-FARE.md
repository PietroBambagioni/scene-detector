# Da fare — tutto ciò che resta aperto

> Indice unico dei punti aperti, raccolti da UPGRADE.md, PUNTI-APERTI.md, TRANSIZIONI-GRADUALI.md
> e le due SESSIONE. **Qui c'è la lista; il dettaglio e i numeri stanno nei doc citati.** Aggiornato
> il 24 luglio 2026.
>
> Legenda: 🔴 azionabile ora · 🟡 dipende da altro · 🔵 opportunistico/piccolo · ⛔ deciso, non si fa

---

## 0 · Immediato

- [x] **Committato** (30 lug 2026, `6d00dc8`): il fix volti (`--faces-min-shots`, ora **default
  3**), `--faces-refine` con la soglia separata, la UI a tre livelli e le miniature per shot —
  17 file, 114 test verdi. Resta fuori dal repo `Introduzione al linguaggio del film.md`
  (384 KB, materiale di terzi): da gitignorare o committare, è una decisione sulle licenze.
- [x] **Default `faces-min-shots`** scelto: **3** (65 personaggi su *Rogue One*). `config.py` + `cli.py`.
- [x] **AutoShot — buttato.** Due annotatori ciechi su 40 boundary di *Rogue One* (`prove/annota/`):
  i boundary unici di AutoShot sono stacchi veri nel 67% (Claude) / 40% (Pietro) dei casi contro il
  80% / 73% di TransNet — non paga il +52% di tempo. Rimosso: `detection/models/autoshot/`,
  `confidence.py` (reconcile), `--ensemble`/`--autoshot-weights`, `DetectorKind.autoshot`, registro
  pesi, `einops`, `test_confidence.py`. −922 righe, 82 test verdi. Chiude "AutoShot: tenerlo o
  buttarlo". Resta su disco `weights/autoshot.pth` (57 MB, gitignored, non più scaricato).
- [x] **README §Valutazione** — già riscritto sull'API vera (`prf1(tol)` + `transition_iou`,
  `README.md` §Valutazione). La voce «stale» era stale: `evaluate`/`read_scenes_txt`/`f1_curve`
  non compaiono più nel README. Verificato il 30 lug 2026.

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

### 🔴 Il cluster dei non-volti — misurato su *Rogue One*, 25 lug 2026

Segnalato guardando il catalogo: «Personaggio 23» unisce persone diverse, e l'unico filo è che
**o sono droidi o hanno elmetti mascherati**. Confermato: cluster **22**, 259 volti in 93 shot,
contiene **K-2SO, Darth Vader, gli stormtrooper, un pilota con casco a visiera e una creatura
pelosa** (contact sheet: `prove/faces_sheet.py 22`). ArcFace è addestrato su volti umani scoperti;
su questi produce embedding che descrivono «oggetto scuro a forma di testa», non identità.

**Tre rimedi plausibili, tutti smontati dalla misura** (cache embedding `prove/faces-Rogue.One/`,
riproduce la produzione byte per byte):

| ipotesi | esito |
|---|---|
| il cluster è *lasco*, si becca dalla coesione | ❌ 0,722 contro 0,746 mediano: **normale** |
| sta in una regione "generica" dello spazio | ❌ cos(centroide, media globale) 0,283, in mezzo ai legittimi (0,14-0,69) |
| alzare `--faces-min-score` | ⚠️ accusa ma non separa (sotto) |
| stringere la soglia di clustering | ⚠️ scambia fusione con frammentazione (sotto) |

- **`det_score` è un buon rilevatore di cluster sospetti e un pessimo separatore.** Mediana 0,579
  (cluster 22) e 0,568 (cluster 85) contro 0,762 di tutti gli altri, e il p90 del 22 (0,68) sta
  **sotto il p10 di ogni cluster legittimo** (0,69). Ma *dentro*, K-2SO compare a **0,50 e a 0,81**,
  Vader a 0,56 e 0,66. Alzare la soglia a 0,65 taglia l'82% del cluster, costa il **12% di tutti i
  volti del film**, e lascia comunque K-2SO e Vader insieme.
- **Nessuna soglia di clustering funziona.** A 0,55 il cluster si spacca in 120/55/34/31: il gruppo
  da 55 è **K-2SO puro** (16/16 verificati), ma quello da 120 è ancora K-2SO + Vader + stormtrooper
  + pilota. Si frammenta l'identità che funzionava senza isolare quelle che non funzionano.
- **Non c'è un salto nella distribuzione**: le mediane di `det_score` per cluster vanno da 0,568 a
  0,881 in continuo, quindi «scarta sotto X» è una taratura su un film solo, non una scoperta.

**Il danno vero non è la card sbagliata**: il nome del cluster entra nel prompt del VLM
(`build_prompt`), quindi 93 shot verrebbero descritti citando un personaggio inesistente.

✅ **Fatto — si marcano, non si scartano** (25 lug 2026). `recognition/faces.mark_uncertain`:
mediana di `det_score` per cluster, sotto `UNCERTAIN_DET = 0,65` il cluster prende
`uncertain: True` e `det_median`. Conseguenze: **fuori dal prompt del VLM**
(`captioning/caption.py`, o un nome sbagliato entra nella descrizione di decine di shot) e
segnalato nella UI (card in trasparenza, `⚠`, tooltip che spiega). Resta visibile e rinominabile:
il giudizio su chi sia davvero lo può dare solo una persona.

Su *Rogue One*: **10 personaggi su 65** segnati, **174 shot** perdono un nome nel prompt — 93 dal
solo cluster 22, il resto cluster da 3-8 shot. La soglia cade fra 0,638 e 0,653, che è il punto più
arbitrario di tutta la faccenda: prende i due colpevoli grossi, e il danno collaterale sono
personaggi piccoli e mal illuminati che perdono il nome in poche descrizioni.

⛔ **Ibrido ArcFace + SigLIP — valutato e scartato.** L'idea ovvia era: ArcFace come primario, e sui
cluster segnalati si ri-clusterizza con SigLIP. Applicata ai nostri dati produce
`{stormtrooper + Vader}`, `{K-2SO chiaro}`, `{K-2SO scuro}`: **scambia un cluster sbagliato con
tre cluster sbagliati**. Vader resta fuso coi trooper e K-2SO si spacca per illuminazione.
Sessanta righe e un modello in più nel percorso volti, per sbagliare in modo diverso. È
esattamente il caso in cui VGG **rifinisce DINOv2 per-film** in contrastivo: senza quell'
addestramento l'apparenza non basta, e quell'addestramento è un altro progetto.

> ⚠️ **Superato in parte** (vedi «Il raffinamento a due stadi» sotto). Il difetto era
> **l'encoder, non lo schema**: con DINOv2 adattato al film, K-2SO non si spacca più per
> illuminazione e l'ibrido funziona. Resta vera la parte su Vader fuso coi trooper.

### Il raffinamento a due stadi — misurato e spedito, 25 lug 2026

`--faces-refine`: ArcFace resta primario, e i **soli** cluster che `mark_uncertain` segnala
(det mediano < 0,65) vengono rimessi in discussione su ritagli di **figura** con DINOv2 (ViT-L
con register, Apache 2.0) più una testa lineare addestrata sul film. Gli umani non passano di
qui per costruzione. Codice: `recognition/embed.py`, `recognition/adapt.py`,
`identify.refine_clusters`, `faces.split_by_reliability`.

**Su *Rogue One*: 65 → 69 personaggi.** Il cluster 22 (259 volti, 93 shot) si scompone in
**175 + 84**, l'85 (86 volti) in **55 + 17 + 9 + 5**. I cluster umani (#6, #5, #1, #14, #2, #0)
restano identici volto per volto. Costo: **+23 min** di embedding sopra i ~50 min della
rilevazione, e **nessuna estrazione ffmpeg in più** — i frame sono già in mano.

A vista, 16 ritagli per cluster: **#22 = K-2SO** (12/16, attraverso shot 749→3046 con
illuminazione radicalmente diversa — esterno chiaro, interno blu, fumo, notte), **#661 = Vader
+ stormtrooper**. Cioè separa **il droide dagli umani in elmetto**, che è quanto SigLIP non
sapeva fare senza spaccare K-2SO. ⚠️ **La purezza non è misurata**: 16 ritagli guardati, non un
numero. Serve l'annotazione (metrica VPCD, sotto).

**Due strade provate e bocciate prima di arrivarci** — entrambe con la misura, non per opinione:

- ⛔ **DINOv2 grezzo sui ritagli di figura.** **Nessuna soglia funziona.** Sotto 0,85 fonde i due
  protagonisti umani (cluster 5 e 6), sopra li polverizza — 240 ritagli → 205 gruppi, i due
  gruppi principali ne catturano il 5%. ArcFace, per confronto, non li confonde **mai**, a
  nessuna soglia. Le contact sheet confermano che i ritagli sono buoni (armatura, mantello,
  corpo del droide ben visibili): non è geometria, è che il coseno di DINOv2 non è allineato
  all'identità. Banco: `prove/body_ab.py`.
  - 📌 Da correggere in `appearance_ab.py`: quella prova usava `PAD = 0,6`, cioè **testa e
    spalle, non figura**. La tesi vera di VGG — box di corpo — non era stata testata fino a qui.
- ⛔ **Adattatore contrastivo auto-supervisionato «stesso shot = stessa identità».** Sembra
  gratis: il 77% degli shot ha esattamente un volto per frame campionato, 14 214 coppie
  positive senza tracking né ArcFace. **Peggiora**: 240 ritagli umani → 71 gruppi già alla
  soglia più larga. Il motivo è aritmetico — **8 191 positivi dichiarati contro 2 676 785
  coppie della stessa identità finite fra i negativi** (17,7% di tutte le coppie). La testa
  impara l'identità dello *shot*, non del personaggio. Banco: `prove/adapt_ab.py`.
  - 🔑 **E vale anche per le tracce: una traccia non attraversa uno stacco.** Da dentro lo shot
    non arrivano positivi cross-shot, mai. Chi propone i body-track per risolvere questo deve
    rispondere prima a questa riga.

**Quello che funziona, e non costa dati esterni**: i cluster ArcFace **affidabili** del film
stesso fanno da maestri. Sui volti umani scoperti ArcFace lega correttamente attraverso gli
stacchi, quindi dà positivi cross-shot veri e gratis — su *Rogue One* 21 identità maestre,
130 196 coppie. L'ipotesi che regge alla misura: *ciò che varia fra uno shot e l'altro — luce,
posa, scala, sfondo — è proprietà della fotografia del film, non del personaggio*, e imparato
sugli umani si applica anche ai non-umani. Effetto isolato (`prove/transfer_ab.py`): a parità di
cattura, i gruppi sui due protagonisti passano da **20 a 7**.

**Perché conta per la coda lunga**: non serve un character bank. Il bank esiste per Star Wars e
non per *Anna*, e questo percorso funziona identico sui due.

- [ ] 🔴 **Purezza vera del raffinamento.** I numeri sopra sono conteggi e un colpo d'occhio su
  16 ritagli. Annotare i 259 del cluster 22 (e i 86 dell'85) chiude la domanda.
### ✅ Vader separato dai trooper — era una soglia, non un modello (26 lug 2026)

**Il difetto era mio e stava in una riga**: `_refine` riusava `faces_threshold` (0,50), che è
tarato sullo spazio **ArcFace**, per clusterizzare nello spazio **DINOv2 adattato**. Le due
distribuzioni di similarità non sono commensurabili — è l'avviso che sta scritto in
`prove/body_ab.py` e che ho ignorato scrivendo il codice.

Misurato con verità annotata a mano (`prove/labels-661.txt`: 84 ritagli, 36 Vader, 35
stormtrooper, 13 altro — maschere col respiratore, piloti TIE, incappucciati):

| | t=0,50 (spedito) | **t=0,70** (corretto) |
|---|---|---|
| #661 | 84 misti — vader 36 + trooper 35 + altro 13 | **36, tutti Vader** |
| #662 | — | **26, tutti stormtrooper** |
| #664 | — | 7, tutti stormtrooper |
| purezza pesata | **0,43** | **0,98** |
| cluster 22 si scompone in | 2 gruppi | **9 gruppi** |

Nuovo campo `Config.faces_refine_threshold` (default 0,70) e `--faces-refine-threshold`, separato
di proposito: **due spazi di embedding diversi non condividono una soglia**.

⚠️ Attenzione a cosa si chiede: *trooper A contro trooper B* non è separabile da nessuna feature
visiva — sono identici per progetto, e VGG dichiara lo stesso limite sui personaggi identici. I
26+7 sopra sono trooper puri ma **frammentati**, e va bene così.

### ⛔ MovieNet — scaricato, addestrato, non ripaga (26 lug 2026)

L'ipotesi era: la testa ha 21 identità maestre di un film solo, con **3 087 identità su 573
film** dovrebbe andare molto meglio. Fatto per davvero — 162 GB di keyframe, 187 404 ritagli di
corpo, 154 minuti di embedding DINOv2, SupCon a campionamento P×K (48×4; il full-batch avrebbe
voluto una matrice 187k×187k, ~140 GB).

Valutazione **senza soglia** sulle coppie cross-shot dei ritagli con verità nota, perché
confrontare la purezza di due spazi alla stessa soglia coseno non vuol dire niente:

| spazio | AUC | AP | purezza@3gruppi |
|---|---|---|---|
| DINOv2 grezzo | 0,944 | 0,951 | 0,96 |
| testa per-film (21 maestri) | 0,944 | 0,940 | 0,52 |
| **testa MovieNet (3 087 maestri)** | **0,948** | **0,956** | 0,96 |
| MovieNet → per-film | 0,950 | 0,944 | 0,96 |

**+0,004 di AUC per 162 GB e mezza giornata.** L'ipotesi «serve più supervisione» è smentita:
il collo di bottiglia non erano né le feature né la quantità di maestri — era la soglia.

📌 **Errore di metodo da non ripetere**: la riga `purezza@3gruppi` sopra ha inizialmente fatto
concludere che la testa per-film *danneggiasse* la separazione (0,52 contro 0,96 del grezzo). È
falso: `purity_at_k` cercava 3 gruppi, e nello spazio adattato quel numero cade a t=0,59, un
punto di lavoro pessimo. A t=0,70 lo stesso spazio dà **0,98**, meglio del grezzo a qualunque
soglia. **Una metrica che sceglie da sé il punto di lavoro può scegliere quello sbagliato.**

I dati restano in `datasets/movienet/` (hard link, zero spazio in più) e l'accesso è in
`prove/movienet.py`: se un giorno serve un banco esterno con identità non-umane, è già lì.

  🔑 **Ma il soffitto non è DINOv2 — è la supervisione. Misurato** (`prove/probe_ab.py`,
  etichette in `prove/labels-661.txt`). #661 annotato a vista: **36 Vader, 35 stormtrooper,
  13 altro** (mascherato col respiratore, piloti TIE, incappucciati). Un probe lineare
  supervisionato sugli embedding DINOv2 **grezzi** separa Vader dai trooper a **1,00**.

  | misura | esito |
  |---|---|
  | CV per shot, 5 fold | **1,00 ± 0,00** |
  | holdout **per contesto** (A→B e B→A) | **1,00** |
  | etichette permutate per shot (controllo) | **0,50 ± 0,18** (max 0,77) |

  Le due righe di controllo servono entrambe. L'holdout per contesto addestra su Vader nel
  corridoio scuro + trooper in pieno sole e testa su Vader nello spazio + trooper in un interno
  rosso: se il probe avesse imparato la *scena* invece dell'identità, lì crollava. E il 1,00 con
  1024 feature su 71 campioni è sospetto per pura aritmetica — 71 punti in 1024 dimensioni sono
  quasi sempre separabili — ma con le etichette permutate scende a 0,50, quindi il segnale è reale.

  **Conseguenza operativa**: l'informazione c'è già negli embedding che calcoliamo, e il
  clustering non la sfrutta perché la testa ha **21 identità maestre di un film solo**. Non
  serve un encoder migliore: serve più supervisione. È l'argomento per addestrare la testa su
  MovieNet e CMD-AM — e si può fare **senza backprop attraverso il ViT**, precalcolando gli
  embedding una volta e addestrando solo la testa.

- [ ] 🟢 **MovieNet — verificato, va bene** (25 lug 2026). Le annotazioni **non** richiedono la
  registrazione OpenDataLab: il mirror HF [`ZhengPeng7/MovieNet`](https://huggingface.co/datasets/ZhengPeng7/MovieNet)
  espone `annotation.v1.zip` (53 MB) e `meta.v1.zip` (537 MB) senza gate. Sono JSON, non pickle:
  nessun rischio di esecuzione, a differenza di `evaluation/shot_dataset.py`.

  | | |
  |---|---|
  | box **di corpo** con identità | **808 051** su **630** film |
  | identità uniche (attori IMDb) | **3 349** — contro le 21 di un film solo |
  | schema | `body.bbox`, `pid` (id IMDb), `shot_idx`, `resolution` |
  | box di **volto** | **zero** nei film controllati: è un dataset di corpi |

  ✅ **Il dubbio era «l'identità è l'attore accreditato, quindi i mascherati non ci sono». È
  falso, e non solo per Star Wars.** Fuori da quella saga: **~35 film, ~45 identità, ~11 000
  istanze**, distribuite su tutti i tipi che ci servono — maschera integrale (Spider-Man 803+800,
  Rorschach 454, V 397, Batman 332+285, Catwoman 323, Green Goblin 280, Jason Voorhees 172),
  protesi (Hellboy 671, Edward Scissorhands 328, Abe Sapien 90, Penguin 264), mocap e CG
  (Jake Sully 1108, Neytiri 416, Caesar 436, *Planet of the Apes* 1968 **e** 2001 **e** 2011),
  robot e androidi (Terminator 608, T-1000 250, David di *Prometheus* 392, David di *A.I.* 466,
  Call 292), trucco pesante (Joker 327 e 218, Freddy Krueger 189). In Star Wars: Vader 225,
  C-3PO 281, Chewbacca 272, R2-D2 71 — un droide senza volto né geometria umana, annotato.

  ✅ **I keyframe a 240p non sono un problema**, che era l'altro dubbio: i box di corpo occupano
  il **93% dell'altezza del frame** (mediana; p10 0,60), quindi a 240p il ritaglio mediano è alto
  **~223 px** — l'input di DINOv2 è 224.

  ⚠️ **Ma la parte non-umana è modesta**: ~11 000 istanze su 808 051. Non è quello il valore.
  Il valore è che l'**invarianza** si impara dalle 3 349 identità su 630 fotografie diverse, e
  poi si applica ai non-umani — che è precisamente ciò che `prove/transfer_ab.py` ha già
  misurato in piccolo (21 maestri, frammentazione 20 → 7). Il sottoinsieme non-umano è il
  **banco di validazione**, non il corpo dell'addestramento.
- [ ] 🔵 **Il cluster 85 si è spezzato in 4** (55/17/9/5) e nessuno ha guardato cosa siano.
- [ ] 🔵 **I nuovi cluster restano `uncertain`** (incerti 10 → 14), quindi fuori dal prompt del
  VLM. Logica non toccata di proposito: se un cluster raffinato è puro, il suo «Personaggio N»
  non è più un nome sbagliato — ma è una decisione da prendere con la purezza in mano.

**Come si risolve davvero, in ordine di costo:**

1. 🟡 **La voce** — è la strada che il repo già percorre per altri motivi. Diarizzazione (§5, Fase 2)
   → embedding vocale per parlante → si lega al cluster visivo per co-occorrenza. K-2SO e Vader
   hanno voci inconfondibili proprio dove il visivo fallisce, ed è il terzo pilastro sia di VPCD sia
   del paper VGG. **Limite da mettere in conto prima di provarci:** funziona solo su chi parla — gli
   stormtrooper del cluster 22 restano indistinguibili.
2. 🔴 **Il VLM come *verificatore*, non come battezzatore** — provato (`prove/vlm_naming.py`,
   Qwen3-VL-8B-4bit, 4 ritagli per cluster, due domande: «è lo stesso personaggio?» e «chi è?»).

   | cluster | verdetto «STESSO» | nomi |
   |---|---|---|
   | 22 (incerto) | **no** ✅ | Stormtrooper, Darth Vader, *C-3PO* (è K-2SO), «spia» |
   | 85 (incerto) | **no** ✅ | «non lo so» ✅ |
   | 6 (controllo umano) | **sì** ✅ | Jyn Erso ✅ |
   | 5 (controllo umano) | **sì** ✅ | «Chirrut Înghil» |
   | 1 (controllo umano) | **sì** ✅ | «Chirrut Îmwe» |

   **La verifica è 5/5**, i due incerti riconosciuti come misti e i tre legittimi come puri.
   **Il nome no**: K-2SO diventa C-3PO (giusta la famiglia, sbagliato il personaggio) e soprattutto
   i cluster 1 e 5 prendono lo stesso nome pur avendo **coseno 0,101** fra i centroidi — due volti
   completamente diversi. Non è frammentazione, è allucinazione.

   Il pezzo che vale è quindi quello che **non richiede di conoscere il film**: un controllo di
   purezza dei cluster, cioè la «metrica di purezza» aperta in §2 da sempre. Il nome resta un
   suggerimento da mostrare, mai da scrivere nel manifest.

   **Misurato sul serio** (`prove/vlm_purity.py`), con un ground truth **costruito**, che non
   chiede a nessuno di riconoscere nessuno: un gruppo di ritagli presi da un solo cluster è puro
   *per costruzione*, uno che ne mescola due è misto *per costruzione*.

   | banco | misto | puro | nomi «non lo so» |
   |---|---|---|---|
   | *Rogue One*, 40 casi | **20/20 = 100%** | 16/20 = 80% | **39/40** |
   | *Anna*, 12 casi (misto soltanto) | **10/12 = 83%** | — | **12/12** |

   ✅ **L'obiezione «su un film ignoto allucina» non regge — ma solo con il prompt giusto.** *Anna*
   (Grifi/Sarchielli, video-arte italiana anni '70) è l'opposto di un blockbuster, e il modello
   **non ha inventato un solo nome**: 12 volte su 12 «non lo so», e il verdetto ha comunque tenuto
   l'83%. L'allucinazione del pilota (due volti a coseno **0,101** battezzati entrambi «Chirrut»)
   veniva dal prompt, che diceva *«un algoritmo sostiene che siano lo stesso personaggio»* e poi
   chiedeva i nomi: **suggerire una conclusione basta a farla confermare**. Con un prompt neutro
   più «non tirare a indovinare», l'invenzione sparisce.
   - **Il prezzo**: con il prompt onesto smette anche di nominare *Jyn Erso*, che prima azzeccava.
     Cioè non c'è un prompt che dia nomi affidabili: **verificatore sì, battezzatore no**, misurato
     due volte in due direzioni.
   - **I 4 falsi positivi**: cluster 8, 41, 7, 18 giudicati misti pur essendo puri. Tre hanno
     coesione (0,79-0,86) e `det` (0,76-0,78) del tutto normali — errori veri. Il quarto è il
     cluster **18**, che la nostra regola già segna `uncertain` (det 0,622): lì il VLM ha ragione e
     il "falso positivo" è dell'etichetta, non sua.
   - ⚠️ **Le due righe della tabella non si confrontano fra loro**: *Anna* usa 2 miniature piccole
     per caso, *Rogue One* 4 ritagli a 640 px. Stesso protocollo, condizioni diverse.
3. ✅ **Rifinire un encoder di apparenza per-film**, come VGG. ~~Fuori scala: serve un character
   bank e un addestramento.~~ **Falso, misurato il 25 lug 2026** — vedi «Il raffinamento a due
   stadi». Il bank non serve (i cluster ArcFace affidabili del film fanno da maestri) e
   l'addestramento è una testa lineare su embedding già calcolati: **secondi**, non un progetto.
   Quello che serviva davvero non era scala, era capire da dove vengono i positivi *cross-shot*.

### Ricognizione — come si riconoscono i personaggi nei film (25 lug 2026)

**Lo stato dell'arte dice esattamente la nostra diagnosi.** VGG Oxford, *Character-Centric
Understanding of Animated Movies* ([arXiv 2509.12204](https://arxiv.org/html/2509.12204), set
2025), su 75 film animati: i personaggi non umani mandano fuori strada il riconoscimento facciale,
e la risposta è cambiare **feature**, non tarare. Usano **DINOv2 su ritagli di corpo** (non di
volto) + voce **ECAPA-TDNN** + tracce da SAM2. Risultato: **81,8 AP contro 45,3 di InsightFace** —
cioè contro il nostro stesso rilevatore. Codice e dataset (CMD-AM) pubblicati.

Prima di loro, e già citato in PUNTI-APERTI §2.5: **VPCD** — Brown, Kalogeiton, Zisserman,
*Face, Body, Voice* ([ICCV-W 2021](https://arxiv.org/pdf/2105.09939),
[codice](https://github.com/Andrew-Brown1/Video_Person_Clustering)) — clustering multimodale con
face-track, body-track e voice-track. Anche Disney è passata al deep learning per i personaggi
animati per lo stesso motivo: i metodi facciali pretendono due occhi, un naso e una bocca in
proporzioni umane.

**Provato in casa, non solo letto** (`prove/appearance_ab.py`, 360 ritagli, SigLIP che nel repo
c'era già). L'idea: se il problema è che ArcFace codifica *identità facciale*, un encoder di
*apparenza* dovrebbe separare un droide da un elmetto.

| soglia | cluster 22 (i non-volti) | due protagonisti **umani** |
|---|---|---|
| 0,80 | 1 gruppo da 114: non separa | 1 gruppo, purezza 0,50: **fonde i due** |
| 0,85 | **55 / 37 / 15**: separa | purezza 0,97, 2 gruppi ancora misti |
| 0,90 | 60 / 16 / 14 | purezza 1,00 ma **35 gruppi per 2 persone** |

Contact sheet dei tre gruppi a 0,85 (`prove/siglip-22.png`): **gruppo 0 = elmetti** (stormtrooper
*e* Vader insieme), **gruppi 4 e 5 = K-2SO**, separati fra loro solo dall'illuminazione. Cioè
SigLIP isola il droide dagli umani in elmetto — cosa che ArcFace non sa fare — ma **fonde Vader
con i trooper e spacca K-2SO per luce**. È apparenza, non identità.

**Conclusione: gli embedding di apparenza sono complementari, non sostitutivi, e presi
dallo scaffale non bastano.** ArcFace è ottimo sui volti umani e catastrofico sui non-volti;
SigLIP l'opposto. Questo spiega anche perché VGG **rifinisce DINOv2 per-film** in contrastivo su
un character bank invece di usarlo così com'è: la nostra misura riproduce indipendentemente il
motivo di quel passaggio.

**La strada realistica per questo repo è la voce**, e converge con quello che è già in programma:
la diarizzazione (§5, Fase 2) darebbe embedding vocali per personaggio, e K-2SO e Vader hanno voci
inconfondibili proprio dove il visivo fallisce. È lo stesso terzo pilastro di VPCD e del paper VGG.
Da fare **dopo** la 4.4, non prima.

- [ ] 🔴 **Cast stantio nel catalogo.** `clips/Rogue.One/manifest.json` ha **113** personaggi da un
  run con `min_shots=2`; il default è **3** e darebbe **65**. Il ramo di resume dello step faces
  riusa `prior["cast"]` senza controllare con quali parametri era stato costruito, quindi rilanciare
  con parametri diversi **non** ricalcola. Serve almeno registrare i parametri accanto al cast.
- [ ] 🔵 **`prove/faces_sheet.py`** — contact sheet di un cluster ordinata per `det_score`, con il
  valore stampato. È lo strumento che ha chiuso questa diagnosi in una schermata; oggi legge le
  label da `/tmp/lab.npy`, cioè è ancora usa-e-getta (vedi la voce «provino del cast» sotto).

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
- [ ] 🔴 **Diarizzazione + linking (Fase 2).** `speech diarize` (Homebrew, binario esterno, niente
  token HF).
  - [x] **Passo 1 spedito** (30 lug 2026): `--diarize` → `transcription/diarize.py`, campo
    `speakers` per shot nel manifest, parlanti nel dettaglio della UI. Indipendente da `--asr`:
    dice *chi* parla, non cosa. Su 600 s di *Rogue One*: 288 shot, 96 con parlanti, 6 parlanti,
    4,5 s. **68 coppie di shot consecutivi su 287 condividono un parlante** — il segnale «stessa
    scena» di §5 esiste ed è denso, ora è nel manifest e si può misurare.
  - Ordine di ciò che resta: linking speaker↔volto per co-occorrenza → nomi dai vocativi
  come `name_hint`+score (non sovrascrivere `Personaggio N`) → poi active speaker detection se
  serve. La dipendenza da 4.4 (cluster volti stabili) è **sciolta**: clustering a due stadi e
  `--faces-refine` sono in `main`.
  - [x] **Sortformer ~4 speaker: confermato, e per questo l'engine di default è `pyannote`**
    (30 lug 2026). Sullo stesso audio sortformer trova **4 esatti**, pyannote e community1 **6**;
    pyannote costa 11 s su 600 s, cioè ~2,5 min su un film. Il «pyannote è gated» non vale dentro
    `speech`. Numeri e caveat in [PUNTI-APERTI §3.5](PUNTI-APERTI.md).
  - ⚠️ **Il banco va deciso prima del linking, non dopo.** BBC Planet Earth ha un narratore solo:
    inutile per la voce. Su RAI va verificato se il parlato è multi-parlante — se lo è, il segnale
    «parlante che attraversa lo stacco» si misura sui suoi 116 confini contro lo 0,388 attuale.
    Altrimenti la Fase 2 resta *plausibile e non giudicabile*, che è la trappola di §0.1.
  - [ ] 🔵 **`speech embed-speaker`** — gallery vocale per personaggio, linking voce↔volto più solido
    che passare per i nomi.
  - [x] **Parlante che attraversa lo stacco — misurato su RAI, 30 lug 2026: indizio, non
    risultato, e il banco è inadeguato.** `prove/rai_diar_ab.py`, 10 video diarizzati (~2 min),
    1225 coppie di shot consecutivi contro i confini di scena annotati.

    **La formulazione letterale — «condividono almeno un parlante» — non è misurabile qui**:
    satura a 853 coppie su 1225 «condiviso» contro **28** «disgiunto». Il parlato copre il 61-96%
    del tempo e basta che il conduttore compaia in entrambi gli shot perché l'intersezione non sia
    vuota. Con 28 casi informativi la potenza è nulla (p = 0,49 e 0,66): **non dice nulla**, né a
    favore né contro.

    Riprovato con «**cambia chi parla di più**» — post-hoc, deciso dopo aver visto saturare la
    prima:

    | criterio | tol | condiviso | disgiunto | rapporto | Fisher 1 coda |
    |---|---|---|---|---|---|
    | dominante | 5 | 0,088 (69/788) | 0,140 (13/93) | 1,66× | 0,078 |
    | dominante | 25 | 0,109 (86/788) | **0,194** (18/93) | **1,74×** | **0,017** |

    L'effetto è nella direzione della tesi e coerente su entrambe le tolleranze. **Ma**: è la
    seconda operazionalizzazione provata sullo stesso dato, cioè 4 test — con Bonferroni p = 0,069,
    fuori dal 5%. E il costo pratico è alto: solo **93 coppie su 1225** hanno un cambio di
    dominante e contengono 18 dei 136 confini, cioè **recall 13% a precisione 0,19**. Da solo non
    sposta OSG (0,388), e infilarlo nel DP adesso significherebbe tarare su un banco debole.

    ⚠️ **Perché RAI non basta, in una riga**: due video su dieci hanno il 99-100% del parlato da un
    solo speaker, quindi per costruzione non possono produrre il segnale. Serve materiale
    **dialogato** con GT di scena — che in casa non c'è: BBC ha un narratore, MovieNet-SSeg ha i
    confini ma non l'audio. È la stessa carenza di banco che blocca il linking voce↔volto.
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
