# Le transizioni graduali — dall'ipotesi al codice

> Indagine del 23 luglio 2026, dal dubbio «il difetto sulle graduali è nostro o del modello?»
> fino alla modifica in produzione. Complemento a
> [SESSIONE-2026-07-23.md](SESSIONE-2026-07-23.md), da cui questa parte è stata estratta: lì
> restano §5.1-5.7, cioè l'esperimento originale sulle corse e la misura di `min_scene_len`.
> I dati grezzi stanno in `prove/`, che non è versionata.

## Il risultato in una tabella

Su ClipShots, 1634 transizioni reali annotate col loro range, IoU >= 0,5:

| | stacchi netti | tutte |
|---|---|---|
| pipeline prima di oggi | 0,81 | 0,088 |
| **pipeline dopo** | **0,93** | **0,270** |

**Tre volte il recall, +12 punti sugli stacchi**, al prezzo di +32% di shot su un film. Il
guadagno sugli stacchi non era atteso: la soglia bassa non serve solo alle dissolvenze, trova
anche cut che a 0,5 restavano sotto.

## Da dove si partiva

§5 aveva dimostrato che la larghezza delle transizioni **è** nelle `probs` e che
`probs_to_ranges` la schiaccia. Ma §5.3 si era fermata: sul test set di SHOT ci sono **sette**
dissolvenze sopra i 15 frame in tutto, e su sette casi qualunque numero è aneddoto. Serviva
materiale con dissolvenze vere, e non esisteva in casa.

## Cosa esiste, cosa no — la ricognizione dei dataset

| dataset | graduali col range | esito |
|---|---|---|
| **ClipShots** `only_gradual` | **5991** su 257 video | ✅ **adottato**, vedi sotto |
| MSU SBD | 3382, tipizzate | download non documentato, va richiesto |
| RAI (AImageLab) | — | il pacchetto pubblico annota **scene**, non shot |
| BBC Planet Earth | — | cartella Drive vuota o inaccessibile |
| OVSD | — | annota scene, non shot |
| HF `it-just-works/sbd` | — | clip da 61 frame etichettate C/T/E, nessuna larghezza |
| TransVLM (2026) | 45 239 | «coming soon», codice non rilasciato |

**Sul download di ClipShots.** 46 GB in tre pezzi di un `tar.gz` su Drive, con `b` e `c`
bloccati da quota. Ma l'archivio ha `only_gradual` (1761 video) e `test` (501) **entrambi
all'inizio del primo pezzo**: ne bastano 18 GB, e dei 257 video estratti restano **2,8 GB**.
`b` e `c` contengono solo `train/`. ⚠️ La quota Drive è reale: riscaricare non è dato per
scontato, per questo i 257 video sono stati estratti prima di cancellare l'archivio.

### 5.8 · Le graduali sul cinema — ground truth **generato**, non annotato

§5.3 era morto su **n=7**: sette dissolvenze sopra i 15 frame in tutto il test set, e su sette
casi qualunque numero è aneddoto. Il dato non esiste in nessun dataset pubblico *sul cinema*
(RAI e BBC sono broadcast, OVSD annota le scene non gli shot, il benchmark di TransVLM è
«coming soon»). Ma non serve cercarlo: **`ffmpeg` sa costruire una dissolvenza di larghezza
esatta**, e il ground truth viene per costruzione, al frame, gratis.

`prove/xfade_sweep.py`: spezzoni veri da *Rogue One* (grana, grading, movimento — sintetica è
solo la giunta), **5 tipi × 10 larghezze × 6 ripetizioni = 300 transizioni**, n=30 per larghezza.

#### Due errori di metodo, entrambi presi da un controllo e non da un'intuizione

**Il self-check, al primo colpo.** `GT sfalsato: intermedi [89…], atteso [88…]`. Il frame `off`
del blend ha peso **0** sul secondo input — è ancora il primo spezzone, pixel per pixel (16,00
esatti contro 43,56 del successivo). Il buco vero è largo **d − 1**, e un `xfade` da 1 frame è
uno stacco netto. Era §5.1 daccapo, in un'altra veste.

**La precision, al secondo giro.** Veniva 0,04-0,17 con `n_pred` a 450-790 contro 300 transizioni
vere: troppo bassa per essere vera. *Rogue One* ha **ASL 3,04 s** e mediana 2,25, quindi uno
spezzone da 4 s preso a caso contiene un taglio vero del montaggio nel **79% dei casi**. Il
detector li trovava — correttamente — ma il ground truth generato non li conosceva, e finivano
fra i falsi positivi; competendo nel matching greedy comprimevano anche il recall. **Misuravo il
mio campionamento, non il detector.** `safe_starts` ora prende gli spezzoni *dentro* un singolo
shot, usando i 2478 boundary che `detect_ab.py` aveva già calcolato su questo film. `n_pred`
scende a 172-582.

> È la stessa famiglia di §4, spostata a monte: non un numero letto senza la sua condizione, ma
> un **dato costruito** senza la sua condizione. E come in §5.1, a trovarlo è stato un controllo
> di sanità, non il ragionamento.

#### Il risultato

`recall / mean IoU`, aggregato sui 5 tipi, n=30 per larghezza:

| larghezza (frame) | 0 | 1 | 2 | 4 | 7 | 11 | 15 | 23 | 31 | 47 |
|---|---|---|---|---|---|---|---|---|---|---|
| TransNet 0,50 pipeline *(oggi)* | .60/.73 | .60/.30 | .33/.58 | .50/.31 | **.00**/.22 | .00/.15 | .00/.11 | .00/.05 | .00/.05 | .00/.02 |
| TransNet 0,20 corse | .60/.73 | .53/.43 | .43/.52 | .47/.50 | .40/.38 | .03/.27 | .03/.23 | .00/.17 | .00/.14 | .00/.09 |
| TransNet 0,05 corse | .60/.71 | .20/.35 | .67/.52 | .70/.59 | .70/.58 | .47/.51 | .37/.41 | .17/.36 | .10/.28 | .03/.21 |
| **TransNet 0,02 corse** | .60/.68 | .10/.31 | .60/.45 | **.87**/.62 | **.80**/.64 | **.67**/.62 | **.57**/.57 | **.57**/.49 | **.30**/.40 | **.17**/.29 |
| AutoShot 0,02 corse | .60/.72 | .07/.31 | .67/.61 | **.90**/.62 | .43/.51 | .13/.36 | .17/.36 | .00/.24 | .03/.26 | .00/.20 |

**Non c'è nessun muro architetturale.** La pipeline di oggi è a zero da 7 frame in su; a soglia
0,02 con le corse il recall tiene **0,57 fino a 23 frame** — un secondo pieno di dissolvenza. Le
`probs` contengono la larghezza, e il collasso è **tutto** post-processing e soglia. È la
conferma più netta dell'ipotesi §5, e SHOT non poteva darla.

**Per tipo di transizione** (TransNet 0,02 corse, recall):

| | 0 | 2 | 4 | 7 | 11 | 15 | 23 | 31 | 47 |
|---|---|---|---|---|---|---|---|---|---|
| `dissolve` | 1.00 | .67 | **1.00** | .83 | .83 | .83 | .83 | .33 | .33 |
| `fade` | 1.00 | .67 | **1.00** | .83 | .83 | .83 | .67 | .33 | .17 |
| `fadeblack` | 1.00 | .83 | .83 | **1.00** | .67 | .50 | .67 | .33 | .17 |
| `smoothleft` | .00 | .00 | .67 | **1.00** | **1.00** | .67 | .67 | .50 | .17 |
| `wipeleft` | .00 | .83 | .83 | .33 | **.00** | .00 | .00 | .00 | .00 |

Due cose che l'aggregato nascondeva:

- **Sulle dissolvenze vere il recall è 0,83 fino a 23 frame.** Il `0,57` aggregato è una media
  fra tre tipi che tengono e due che no. La transizione con trasparenza — quella che il cinema
  usa davvero — è fra le tre che tengono.
- **I `wipe` sono il caso perso**: zero sopra i 7 frame, a ogni soglia. Non è un problema di
  delimitazione, è che un wipe non produce un picco di differenza fra frame consecutivi — la
  variazione è spaziale, non temporale. Nessuna soglia lo cambia.
- **`w00` a 0,60 non è un difetto del campione** (era la mia lettura del secondo giro, sbagliata):
  è 1,00 sui tre tipi di blend e 0,00 su `wipe`/`smooth`, dove un `xfade` da 1 frame produce un
  frame *ibrido* — mezzo schermo A, mezzo B — che non è né uno stacco né una transizione, e
  sfalsa il taglio di un frame.

#### Il costo: la metrica che decide

| configurazione | P | R | **F1** | n_pred |
|---|---|---|---|---|
| TransNet 0,50 pipeline *(default di oggi)* | 0,341 | 0,203 | 0,255 | 179 |
| TransNet 0,30 corse | 0,259 | 0,220 | 0,238 | 255 |
| TransNet 0,05 corse | 0,263 | 0,400 | 0,317 | 457 |
| **TransNet 0,02 corse** | 0,270 | **0,523** | **0,356** | 582 |
| AutoShot 0,30 pipeline | 0,344 | 0,250 | 0,290 | 218 |

**+10 punti di F1** (0,255 → 0,356), con il recall che passa da 0,20 a 0,52 — **2,6×** — e la
precision che scende di 7 punti. A differenza di §5.7, qui il costo *non* si mangia il guadagno:
il netto è dieci volte quello che `min_scene_len` da solo poteva dare.

I valori assoluti sono bassi perché `min_iou=0,5` su una metrica range-based è severo: una
dissolvenza trovata ma delimitata come un punto non è un TP. È il confronto relativo che conta,
non lo 0,356.

**Cosa misura e cosa no.** `xfade` fa un blend **lineare**; un montatore usa curve diverse e a
volte grada sopra la giunta. Questo è il **tetto**: se il detector non vede una dissolvenza
lineare da 24 frame, non vedrà nemmeno quelle vere. Il contrario non vale, e serve validazione su
dissolvenze reali — ClipShots ha un set `only_gradual` scaricabile, MSU ha 3382 graduali
tipizzate ma il download va richiesto.

### 5.9 · Cosa questo cambia, e cosa resta da fare

**La decisione §5.6 non è più alla pari.** L'opzione B (corse in `probs_to_ranges`) ha ora tre
misure indipendenti a favore, di cui una su cinema, e il guadagno è +10 punti di F1 contro il +1
di A. Resta vero che B cambia il contratto di `probs_to_ranges` e ricadono
`boundary_confidences`, `conf_mod.reconcile` e lo splitter — ma il prezzo del *non* farlo ora ha
un numero.

**E porta con sé la soglia.** Il guadagno vive a 0,02-0,05: al default 0,50 le corse rendono
`+0,002`. **Le due decisioni non sono separabili**, e questo vale anche al contrario — abbassare
la soglia *senza* le corse peggiora tutto (0,255 → 0,076 a 0,02, perché `enforce_min_len`
rifonde ogni scena da 1 frame e la precision crolla senza che il recall salga).

Da fare, in ordine:

1. **Validare su dissolvenze reali.** ClipShots `only_gradual`, scaricabile ora. Il tetto lineare
   dice cosa è possibile, non cosa succede sul montato vero.
2. **Griglia sotto 0,02.** Il migliore è ancora sul bordo inferiore: l'ottimo potrebbe non essere
   in griglia. Costa secondi sulla cache.
3. **Union delle corse dei due modelli.** AutoShot vince sulle strette (0,90 a 4 frame contro
   0,87) e collassa sulle larghe (0,13 a 11 contro 0,67): si specializzano all'opposto.
   `reconcile` oggi lavora su boundary puntuali, quindi non è gratis.
4. **I `wipe` restano scoperti** e nessuna taratura li recupera. Se contano — *Star Wars* li usa
   come marchio di fabbrica — serve un segnale spaziale, che è esattamente ciò che OmniShotCut
   dichiara di modellare. È il primo argomento tecnico a suo favore che non venga da n=7.

### 5.10 · OmniShotCut misurato — vince, e non costa quello che credevamo

Stesso banco di §5.8, stesso ground truth, stessa funzione di accoppiamento: unica variabile il
detector. `prove/omni_ab.py`, due passi perche' OmniShotCut vive in un venv separato
(`prove/.venv_omni`) che non ha `scene_detector`.

**Gira su MPS**, contro quanto dice il suo README. `engine.py` scrive `.to("cuda")` in tre punti
senza parametro di device: si rimappa `cuda` → `mps` intercettando `.to()`, cinque righe a
runtime, nessun fork e nessuna modifica su disco.

**`recall / mean IoU` per larghezza**, aggregato sui 5 tipi:

| larghezza (frame) | 0 | 1 | 2 | 4 | 7 | 11 | 15 | 23 | 31 | 47 |
|---|---|---|---|---|---|---|---|---|---|---|
| TransNet 0,50 pipeline *(oggi)* | **.60**/.73 | **.60**/.30 | .33/.58 | .50/.31 | .00/.22 | .00/.15 | .00/.11 | .00/.05 | .00/.05 | .00/.02 |
| TransNet 0,02 corse *(nostro meglio)* | **.60**/.68 | .10/.31 | **.60**/.45 | .87/.62 | .80/.64 | .67/.62 | .57/.57 | .57/.49 | .30/.40 | .17/.29 |
| **OmniShotCut** | .17/.81 | .07/.34 | .07/.37 | **.80**/**.80** | **.87**/**.86** | **.90**/**.91** | **.80**/**.88** | **.83**/**.89** | **.73**/**.91** | **.57**/**.85** |

| | P | R | **F1** |
|---|---|---|---|
| TransNet 0,50 pipeline | 0,341 | 0,203 | 0,255 |
| TransNet 0,02 corse | 0,270 | 0,523 | 0,356 |
| **OmniShotCut** | **0,821** | **0,580** | **0,680** |

**F1 2,7× il default di oggi**, e quasi 2× il meglio che sappiamo fare con le corse. Ma il numero
che conta di piu' e' l'**IoU: 0,85-0,91** dove noi stiamo a 0,29-0,64. Non e' che trova piu'
transizioni: le **delimita**, che e' esattamente il difetto diagnosticato in §5 e mai risolto.

**Sui `wipe` la previsione di §5.8 e' confermata alla lettera.** Noi: zero sopra i 7 frame, a
ogni soglia, perche' la variazione e' spaziale e non produce picco fra frame consecutivi.
OmniShotCut: **recall 1,00** a 7, 11, 15 e 47 frame, con IoU 0,75-0,96.

**Ma sotto i 4 frame crolla, e li' siamo meglio noi.** Su `w00` fa **0,17** contro il nostro
0,60; su `w01`-`w02` sta a 0,07. Su un film normale gli stacchi netti sono la stragrande
maggioranza dei boundary — *Rogue One* ne ha 2478 quasi tutti netti — quindi **come detector
primario, da solo, non e' adottabile**. I due profili sono complementari, non ordinati.

**Il costo: 660 f/s su MPS, decode incluso.** TransNet fa 390 f/s di sola inference (494 s per i
192 701 frame di *Rogue One*, piu' 50 s di decode a parte). **OmniShotCut e' quasi 2× piu'
veloce dell'intera detection di oggi**, non 4× piu' lento: il «4× il tempo» in
[PUNTI-APERTI.md](PUNTI-APERTI.md) non regge alla misura. ⚠️ Misurato su 4950 frame: il
throughput su un film intero puo' degradare, va rifatto su *Rogue One* prima di dichiararlo.

**Tre convenzioni diverse dalle nostre, e le prime due davano `F1 0,000` su tutto:**

1. Le transizioni sono **range espliciti** alternati agli shot (`[0,85] General · [85,96]
   Dissolve · [96,149] General`), non buchi fra shot.
2. L'estremo destro e' **esclusivo**.
3. Le graduali stanno in `intra` come range etichettati, gli **stacchi netti no**: sono una
   relazione fra range consecutivi, `inter == "Hard_Cut"`. Contando solo `intra`, `w00` restava
   a zero per costruzione.

> **La quarta della famiglia §4/§5.1.** Il primo risultato era `0,000` ovunque — hard cut
> compresi — e quello e' il segnale che ha smascherato il bug: nessun modello pubblicato fa zero
> su uno stacco netto. Un risultato *plausibilmente basso* sarebbe passato.

**Vantaggio di campo, da non dimenticare.** OmniShotCut e' addestrato su una *«fully synthetic
transition synthesis pipeline»* (dal paper) — la stessa famiglia di trasformazioni che `xfade`
produce. Questo banco e' **casa sua**, esattamente come SHOT lo era per AutoShot (§5.5). Il
numero va confermato su montato vero: ClipShots `only_gradual` e' il prossimo passo.

### 5.11 · Su materiale reale il divario sparisce — OmniShotCut pareggia

§5.10 e' misurato su transizioni `xfade`, cioe' in casa di OmniShotCut. Qui: dieci video del
**RAI Dataset** (Rai Scuola, documentari e talk show), montati davvero. `prove/rai_ab.py`.

**Cosa e' misurabile e cosa no.** Il RAI pubblico e' annotato per **scene**, non per shot: i
724 cut + 263 graduali che i paper citano non sono distribuiti — cercati, esiste solo il
riferimento bibliografico. Quindi **recall si'** (un confine di scena e' per forza un confine di
shot: 116 boundary annotati a mano da esperti), **precision no** (gli shot boundary *interni*
alle scene non sono annotati, quindi un predetto non accoppiato non e' un falso positivo — e'
l'errore di §5.8 spostato nella lettura), **larghezza no** (il GT non ce l'ha).

**116 confini di scena, tolleranza 5 frame:**

| configurazione | trovati | recall | n_pred |
|---|---|---|---|
| TransNet 0,50 pipeline *(default di oggi)* | 93/116 | 0,802 | 928 |
| AutoShot 0,50 pipeline | 97/116 | 0,836 | 999 |
| **TransNet 0,02 corse** | **99/116** | **0,853** | 1491 |
| **OmniShotCut** | **99/116** | **0,853** | 1511 |

**Il divario schiacciante di §5.10 non si riproduce.** Sul banco sintetico OmniShotCut faceva
F1 0,680 contro 0,356: qui **pareggia** con le nostre corse, stesso recall e `n_pred` a meno
dell'1,5%. Il vantaggio di campo di §5.5 era reale e vale la meta' del risultato.

**Ma la lettura onesta e' che le due misure rispondono a domande diverse.** Qui si misura
*trovare*, non *delimitare* — e la delimitazione era il punto di forza vero (IoU 0,85-0,91
contro 0,29-0,64). Su questo GT non e' misurabile, e resta la domanda aperta.

**Le corse guadagnano anche qui: 0,802 → 0,853, +5 punti di recall.** Terza conferma
indipendente dopo SHOT (§5.4, +6) e il sintetico (§5.8), la prima su broadcast montato. Il
guadagno regge su tre distribuzioni diverse.

**E AutoShot batte TransNet** (0,836 contro 0,802) a parita' di post-processing e `n_pred`. Sul
cinema §5.8 diceva l'opposto sulle graduali larghe. Il sospetto di §5.5 — che AutoShot vincesse
solo in casa propria — non regge: qui la casa non e' di nessuno dei due.

OmniShotCut marca **292 transizioni come graduali** (`Fade`, `Dissolve`, `Slide`) sui dieci
video: e' metadato che nessuno dei nostri detector produce, indipendentemente da chi trova piu'
boundary.

> **Da fare per chiudere.** Serve un GT con le **larghezze** su materiale reale: l'unico pubblico
> e' ClipShots (46 GB, tar.gz spezzato in tre — o tutto o niente). Il loro protocollo ufficiale
> usa *overlap* semplice invece dell'IoU, con cut = larghezza 1 frame: i numeri sarebbero
> confrontabili con quelli pubblicati nel loro paper.

### 5.12 · ClipShots — la delimitazione su graduali reali, e sono complementari

La domanda lasciata aperta da §5.11: su materiale reale il RAI pubblico da' solo la *posizione*
dei confini, quindi si misurava chi trova, non chi **delimita** — e delimitare era il punto.
ClipShots `only_gradual` annota le graduali **col loro range**: 1634 transizioni su 30 video
scelti per densita' di annotazione, da Youtube e Weibo, montati davvero.

**Il download e' andato meglio del previsto.** 46 GB in tre pezzi, con `b` e `c` bloccati da
quota Drive — ma il dataset e' impacchettato con `only_gradual` (1761 video) e `test` (501)
**entrambi all'inizio di `a`**, e il training set in coda. Bastavano 18 GB dei 46; dei 30 video
che servivano, 495 MB estratti. `b` contiene solo `train/` (+2636 video), `c` il resto.

**`recall / mean IoU` per larghezza, IoU>=0,5** (n = transizioni annotate per bucket):

| | cut | 2-3 | 4-6 | 7-15 | 16-30 | 31-50 | >50 | R tot | n_pred |
|---|---|---|---|---|---|---|---|---|---|
| **n** | 172 | 18 | 53 | 319 | 730 | 292 | 50 | 1634 | |
| TransNet 0,50 pipeline *(oggi)* | .81/**1.00** | .28/.60 | **.00**/.35 | **.00**/.17 | **.00**/.09 | **.00**/.06 | **.00**/.03 | 0,088 | 1518 |
| AutoShot 0,50 pipeline | .78/**1.00** | .06/.67 | **.00**/.32 | **.00**/.17 | **.00**/.09 | **.00**/.06 | **.00**/.03 | 0,083 | 1480 |
| **TransNet 0,02 corse** | **.91**/.92 | **.56**/.58 | **.66**/.63 | **.67**/.60 | .32/.41 | .30/.43 | .10/.27 | **0,455** | 3722 |
| **OmniShotCut** | .33/.94 | .11/.42 | .17/.63 | .36/**.68** | **.43**/**.73** | **.40**/**.72** | **.62**/**.76** | 0,397 | 1429 |

**Il default di oggi manca il 91% delle transizioni annotate** (R 0,088), ed e' a **zero esatto**
da 4 frame in su su 1444 casi reali. Non e' piu' un'inferenza da SHOT o dal sintetico: e' la
misura diretta, su montaggio vero, del difetto diagnosticato in §5. AutoShot fa lo stesso
(0,083): sulla delimitazione i due sono indistinguibili.

**Le corse quintuplicano il recall: 0,088 → 0,455.** E sui cut *migliorano* anche la posizione
(0,91 contro 0,81), quindi non e' un baratto fra graduali e stacchi. Quarta conferma
indipendente, la prima con l'IoU misurato su materiale reale.

**Ma i due profili sono opposti, e questa e' la scoperta.**

- **Stacchi e transizioni strette**: le corse dominano — `.91` contro `.33` sui cut.
- **Graduali larghe**: OmniShotCut domina — su >50 frame `.62` contro `.10`, e su 16-50 tiene
  `.40-.43` dove le corse scendono a `.30-.32`.
- **Delimitazione**: OmniShotCut e' avanti ovunque conti, IoU **0,68-0,76** contro 0,27-0,43
  dalle 7 frame in su. E' esattamente il punto di §5.10, ma stavolta fuori casa sua.

**E lo fa sparando molto meno.** Le corse arrivano a 0,455 con **3722** predizioni, OmniShotCut a
0,397 con **1429** — 2,6× in meno. Senza precision (`only_gradual` non annota tutti i boundary,
quindi un predetto non accoppiato non e' un falso positivo) `n_pred` e' l'unico indicatore del
costo, e dice che il recall delle corse e' comprato caro.

> **La conclusione non e' "chi vince" ma "non competono".** Il recall totale li mette vicini
> (0,455 contro 0,397) nascondendo che coprono meta' del problema ciascuno. Un ensemble corse +
> OmniShotCut e' l'unica configurazione che copra sia gli stacchi sia le dissolvenze lunghe, e
> ora ha i numeri per essere valutato invece che ipotizzato — vedi §5.9 punto 3, che chiedeva
> l'union delle corse dei due *nostri* modelli e trovava che si specializzano all'opposto. Qui
> la specializzazione e' molto piu' marcata, e su materiale reale.

### 5.13 · Quanto costano le corse in shot — molto meno del previsto

Quattro misure dicono che le corse recuperano le graduali, tutte guardando le *transizioni*.
Nessuna guarda il **catalogo**, ed e' li' che il costo si paga: ogni shot in piu' e' una clip su
disco, una card nella UI e una chiamata VLM da ~5 s. `prove/costo_corse.py`, stesse probs di
*Rogue One*, unica variabile il post-processing.

| config | shot | vs oggi | ASL | shot <15f | VLM |
|---|---|---|---|---|---|
| **pipeline 0,50** *(default di oggi)* | 2426 | 1,00× | 3,31 s | 0 | 3,4 h |
| pipeline 0,30 | 2543 | 1,05× | 3,16 s | 0 | 3,5 h |
| pipeline 0,20 | 2593 | 1,07× | 3,10 s | 0 | 3,6 h |
| corse 0,20 | 2747 | 1,13× | 2,93 s | 172 | 3,8 h |
| corse 0,10 | 2975 | 1,23× | 2,70 s | 359 | 4,1 h |
| **corse 0,05** | 3267 | **1,35×** | 2,46 s | 603 | 4,5 h |
| corse 0,02 | 3788 | **1,56×** | 2,12 s | 1051 | 5,3 h |

**Avevo stimato 5900 shot e «oltre 8 ore». Sono 3788 e 5,3 h.** La stima veniva dal rapporto
`n_pred` di §5.12 — 3722 contro 1518, cioe' 2,45× — trasferito a *Rogue One*. Ma ClipShots sono
video Youtube/Weibo brevi e concitati e *Rogue One* e' cinema: **il rapporto non si trasferisce
fra distribuzioni**, e applicarlo era la stessa famiglia di errore di §4, stavolta su un
rapporto invece che su un valore assoluto.

**Il costo vero e' +35% di shot e +1,1 h di VLM a soglia 0,05**, contro +56% e +1,9 h a 0,02; il
grosso della differenza sono i 1051 shot sotto i 15 frame, contro i 603 di 0,05.

⚠️ Il recall che quel costo compra era qui stimato «~0,4» a 0,05. **Misurato in §5.14: 0,325**,
e concentrato sui bucket sbagliati — la stima veniva dal banco sintetico, dove le larghezze sono
distribuite in modo uniforme e non come nel montato reale.

**Gli shot brevi non sono tutti rumore: molti *sono* le dissolvenze**, ed e' esattamente il
punto dell'opzione B (la pipeline oggi li rifonde con `enforce_min_len`, ed e' cosi' che perde
la larghezza). Ma non e' stato verificato quanti dei 603 siano transizioni vere e quanti
spurii — `prove/annota_boundary.py` risponderebbe su un campione cieco.

### 5.14 · La soglia misurata — e la raccomandazione di §5.13 era sbagliata

§5.13 chiudeva con «corse a 0,05, non 0,02: prende la gran parte del recall al 65% del costo».
Misurato su ClipShots, stessi 30 video di §5.12, unica variabile la soglia:

| soglia corse | R tot | n_pred | shot su *Rogue One* | cut | 4-6 | 7-15 | 16-30 | 31-50 | >50 |
|---|---|---|---|---|---|---|---|---|---|
| 0,10 | 0,212 | 3008 | 2975 (1,23×) | **.95** | .42 | .36 | .05 | .01 | .00 |
| 0,05 | 0,325 | 3323 | 3267 (1,35×) | **.95** | .55 | .56 | .18 | .06 | .00 |
| 0,02 | **0,455** | 3722 | 3788 (1,56×) | .91 | **.66** | **.67** | .32 | .30 | .10 |
| *OmniShotCut* | *0,397* | ***1429*** | — | *.33* | *.17* | *.36* | ***.43*** | ***.40*** | ***.62*** |

**«La gran parte del recall al 65% del costo» era falso**: 0,05 prende il **71%** del recall a
fronte dell'**87%** del costo incrementale in shot. E non c'e' nessun ginocchio nella curva — il
rapporto recall/shot fra 0,10→0,05 e 0,05→0,02 e' praticamente identico (0,0094 contro 0,0081
punti di recall per punto percentuale di shot). La raccomandazione era stata scritta guardando
il **totale**, senza controllare dove il recall si perdesse.

**Dove si perde: le graduali larghe sono 1072 delle 1634 annotate — il 66% del ground truth.**
A 0,05 le manchiamo quasi tutte (0,18 / 0,06 / 0,00 sui tre bucket sopra i 15 frame). Il totale
0,325 sembra dignitoso perche' i cut, dove le corse sono eccellenti, pesano nella media.

> **La quinta della famiglia §4.** Stavolta non un numero letto senza la sua condizione, ma una
> **media letta senza la sua distribuzione**. Ed e' lo stesso errore di §2.5 — «aggregate
> insieme, le 55 graduali si annegano in ~2500 hard cut» — commesso di nuovo, undici sezioni
> dopo averlo scritto.

#### La conclusione: abbassare la soglia compra caro cio' che OmniShotCut da' meglio

Le corse a 0,02 arrivano a 0,455 con **3722** predizioni; OmniShotCut a 0,397 con **1429**. E
sulle larghe — i due terzi del problema — non c'e' partita: 0,62 contro 0,10 sopra i 50 frame,
con IoU 0,76 contro 0,27.

**Configurazione raccomandata, e non e' ne' l'una ne' l'altro:**

- **corse a 0,05-0,10** per stacchi e transizioni strette: **0,95** sui cut, meglio di qualunque
  altra cosa misurata, incluso il default di oggi (0,81) e OmniShotCut (0,33);
- **OmniShotCut** per le graduali larghe, dove le corse a qualunque soglia restano indietro e
  dove porta in dote le etichette di transizione, metadato che oggi non abbiamo.

Costo: **+23-35% di shot** invece di +56%, piu' un secondo detector a 660 f/s. E a differenza
dell'ensemble attuale (TransNet + AutoShot, errori correlati per costruzione, §0.4) qui la
seconda opinione e' architetturalmente diversa davvero: DETR con query di shot contro CNN 3D
per-frame.

**Cosa resta da verificare prima di scrivere codice:** la union non e' stata misurata, solo
stimata dai due profili separati. I due potrebbero sovrapporsi piu' del previsto sui bucket
centrali (4-15 frame), dove entrambi prendono qualcosa. E `reconcile` oggi lavora su boundary
puntuali: farlo lavorare su range e' parte del lavoro, non un dettaglio.

### 5.15 · La union misurata — funziona, ed e' la configurazione da adottare

§5.14 raccomandava «corse per stacchi e strette + OmniShotCut per le graduali larghe» **stimando
dai due profili separati**, senza misurare. Misurata: `union()` in `prove/clipshots_ab.py`, che
scarta i doppioni (IoU >= 0,5 fra due predette) invece di concatenare — altrimenti `n_pred`, unico
proxy di costo su questo GT, sarebbe gonfiato proprio nella configurazione da valutare.

| configurazione | cut | 4-6 | 7-15 | 16-30 | 31-50 | >50 | **R tot** | n_pred |
|---|---|---|---|---|---|---|---|---|
| **pipeline 0,50** *(oggi)* | .81 | .00 | .00 | .00 | .00 | .00 | **0,088** | 1518 |
| corse 0,05 | **.95** | .55 | .56 | .18 | .06 | .00 | 0,325 | 3323 |
| OmniShotCut | .33 | .17 | .36 | .43 | .40 | **.62** | 0,397 | **1429** |
| corse 0,10 + Omni | **.95** | .47 | .56 | .46 | .40 | **.62** | 0,531 | 3857 |
| **corse 0,05 + Omni** | **.96** | .57 | .69 | **.56** | .43 | **.62** | **0,606** | 4078 |
| corse 0,02 + Omni | .92 | .66 | **.74** | **.65** | **.59** | **.68** | **0,687** | 4382 |

**R 0,606 contro lo 0,088 di oggi: quasi 7×.** E contro il meglio di un detector solo — 0,455
delle corse a 0,02 — sono +15 punti con **meno** shot dal lato TransNet (soglia 0,05 invece di
0,02, cioe' 3267 shot invece di 3788 su *Rogue One*).

**I tre controlli annunciati prima del run, tutti passati:**

1. **I cut non si degradano**: 0,96, anzi *sopra* lo 0,95 delle corse da sole. OmniShotCut non
   ruba accoppiamenti nel matching greedy — temevo di si', vista la sua tendenza a emettere
   range larghi.
2. **Le larghe si avvicinano a OmniShotCut, e su un bucket lo superano**: su 16-30 frame — il
   piu' popolato, **730 casi su 1634** — la union fa **0,56** contro 0,43 di Omni e 0,18 delle
   corse. Li' i due sbagliano davvero su casi diversi.
3. **`n_pred` 4078 contro i 4752 della somma**: la dedup ne ha tolti 674, il **14%**. I due
   detector si sovrappongono poco — che e' la premessa di tutta la configurazione, e adesso e'
   misurata invece che assunta.

**Il costo onesto: la union diluisce l'IoU di OmniShotCut.** Sulle larghe la delimitazione passa
da 0,73/0,72/0,76 (Omni puro) a 0,58/0,54/0,70, perche' entrano in gioco anche accoppiamenti
con le predette delle corse, meno precise. Si guadagna recall e si perde un po' di precisione
sui contorni: per un catalogo naviga bile e' il baratto giusto, ma va detto.

> **Raccomandazione finale: corse a 0,05 + OmniShotCut.** Lo 0,02 da' 8 punti di recall in piu'
> ma costa +16% di shot sul lato TransNet e peggiora i cut (0,92 contro 0,96) — e i cut sono
> quasi tutti i boundary di un film vero. Lo 0,10 ne perde 7,5 e non fa risparmiare abbastanza.
>
> **Cosa resta da fare prima di scrivere il codice:** questo e' misurato su ClipShots — video
> Youtube/Weibo brevi. Il costo in shot su *Rogue One* e' noto per le corse (3267) ma **non per
> la union**: quanti shot produca OmniShotCut su un film di 134 min non e' stato contato, e la
> fusione dei due va decisa (`reconcile` oggi lavora su boundary puntuali, non su range).

### 5.16 · Implementato — e il path di produzione non e' quello che le corse misuravano

Il codice: `runs_to_ranges` in `detection/neural.py`, `Scene.transition`, il campo `transition`
nel manifest, default `threshold` 0,5 → **0,05** e `min_scene_len` 15 → **5**. 85 test verdi
(79 + 6 nuovi).

**Il contratto non e' stato rotto.** L'ipotesi di §5.6 era che adottare le corse significasse
introdurre buchi fra gli shot, facendo ricadere `boundary_confidences`, `reconcile` e lo
splitter — «~30 righe e piu' rischio». Non serve: una corsa `i..j` e' **una** transizione, lo
shot uscente la include e finisce a `j`, l'entrante parte a `j+1`. I range restano contigui e
coprono tutti i frame; la larghezza, che prima si buttava, diventa un campo del manifest.
Nessuno dei tre consumatori e' stato toccato.

#### La misura che ha cambiato le conclusioni: le corse "nude" sovrastimano

Tutte le tabelle da §5.8 a §5.15 misurano `runs_above`, che **salta `enforce_min_len`**. Il path
di produzione no. Misurati fianco a fianco sugli stessi 30 video:

| | cut | 7-15 | 16-30 | R tot |
|---|---|---|---|---|
| corse 0,05 *nude* | 0,95 | 0,56 | 0,18 | 0,325 |
| **produzione 0,05, `min_len` 15** | **0,77** | 0,33 | 0,11 | 0,215 |
| **produzione 0,05, `min_len` 5** | **0,93** | 0,44 | 0,13 | 0,270 |

Con `min_scene_len=15` i cut vanno **sotto il default di oggi** (0,77 contro 0,81): a soglia
bassa nascono piu' shot brevi legittimi e la fusione cieca ne mangia di veri. Il guadagno delle
corse veniva mangiato dal passaggio successivo, e nessuna delle quattro misure precedenti poteva
vederlo perche' nessuna includeva quel passaggio.

> **§5.7 non era sbagliata, era condizionata.** Aveva assolto `min_scene_len=15` misurandolo a
> soglia **0,20-0,50**, dove i valori sono equivalenti (+1 punto di F1). A 0,05 la stessa
> taratura costa **16 punti sui cut**. Le due decisioni non sono separabili, ed e' la seconda
> coppia di parametri accoppiati trovata oggi (l'altra: corse↔soglia, §5.14).

#### I numeri del default nuovo

Su *Rogue One*, dalle stesse probs:

| | oggi | nuovo |
|---|---|---|
| shot | 2426 | **3204** (+32%) |
| transizioni graduali registrate | 0 | **461** (mediana 2f, max 22f) |
| VLM | 3,4 h | 4,5 h |
| recall su ClipShots | 0,088 | **0,270** |
| di cui sui soli stacchi netti | 0,81 | **0,93** |

**Tre volte il recall e +12 punti sui cut, per +32% di shot e +1,1 h di catalogazione.** Il
guadagno sui cut e' la parte che non ci si aspettava: la soglia bassa non serve solo alle
dissolvenze, trova anche stacchi che a 0,5 restavano sotto.

**Cosa non e' stato fatto:** OmniShotCut resta fuori dalla pipeline. Il suo contributo e'
misurato (§5.15: la union porta il recall da 0,215 a 0,534) ma e' una dipendenza nuova, un
secondo modello da scaricare e una `reconcile` su range da scrivere — decisione separata, non
una taratura.


---

## Gli errori di metodo — sei, tutti presi da un controllo

Sono la parte piu' riutilizzabile di questa giornata: nessuno e' stato trovato ragionando, tutti
da una verifica che *doveva* dare un certo risultato e non lo dava.

| # | errore | come e' emerso |
|---|---|---|
| 1 | **GT sfalsato di un frame.** Il primo frame di un blend `xfade` ha peso 0 sul secondo input: e' ancora lo spezzone A. Il buco vero e' largo `d-1` | `--selfcheck` su due colori uniformi: i frame intermedi misurati non coincidevano con quelli attesi |
| 2 | **Spezzoni con tagli veri dentro.** *Rogue One* ha ASL 3,04 s, gli spezzoni erano da 4 s: il **79%** conteneva un taglio del montaggio, che il GT generato non conosceva | precision 0,04-0,17, troppo bassa per essere vera |
| 3 | **Tre convenzioni di OmniShotCut** diverse dalle nostre: transizioni come range espliciti (non buchi), estremo destro esclusivo, stacchi netti in `inter` e non in `intra` | `F1 0,000` su ogni bucket, **hard cut compresi** — nessun modello pubblicato fa zero su uno stacco |
| 4 | **Un rapporto trasferito fra distribuzioni.** Da `n_pred` di ClipShots avevo stimato 5900 shot su *Rogue One*: sono **3788** | misurato invece che estrapolato |
| 5 | **Una media letta senza la sua distribuzione.** «0,05 prende la gran parte del recall»: falso, le graduali larghe sono il **66%** del GT e a 0,05 si mancano quasi tutte | guardando i bucket invece del totale |
| 6 | **Le corse "nude" sovrastimano.** Tutte le tabelle saltavano `enforce_min_len`; il path di produzione no, e con `min_len=15` i cut andavano **sotto** il default di oggi | misurando il path vero invece del proxy |

> Il filo comune: **un numero troppo netto o troppo storto per essere vero**. Uno zero sugli
> stacchi, una precision a 0,04. Un risultato *plausibilmente mediocre* sarebbe passato — ed e'
> il motivo per cui ogni banco ha almeno un controllo che deve fallire se il metodo e' rotto.

## Le due coppie di parametri accoppiati

Trovate entrambe oggi, ed entrambe invisibili misurando un parametro alla volta:

- **corse ↔ soglia**: le corse al default 0,50 rendono `+0,002`; abbassare la soglia *senza* le
  corse peggiora tutto (F1 0,255 → 0,076). Vanno adottate insieme o non conviene nessuna delle
  due.
- **soglia ↔ `min_scene_len`**: §5.7 aveva assolto `min_len=15` misurandolo a soglia 0,20-0,50,
  dove i valori sono equivalenti. A 0,05 la stessa taratura costa **16 punti sui cut** (0,77
  contro 0,93), perche' nascono piu' shot brevi legittimi e la fusione cieca ne mangia di veri.

## Cosa e' cambiato nel codice

| file | cosa |
|---|---|
| `detection/neural.py` | **`runs_to_ranges`**: una corsa contigua di frame caldi e' *una* transizione, non N tagli. Ritorna `(ranges, transitions)` |
| `core/scene.py` | `Scene.transition` — la giunta che apre lo shot, `None` se stacco netto; `scenes_from_ranges` la propaga |
| `catalog/manifest.py` | campo `transition` `{start_frame, end_frame, n_frames}`, presente solo sulle graduali |
| `core/config.py` · `cli.py` | `threshold` 0,5 → **0,05**, `min_scene_len` 15 → **5** |
| `tests/test_scene.py` | 6 test nuovi (85 verdi in totale) |

**Il contratto non e' stato rotto.** §5.6 prevedeva che le corse introducessero buchi fra gli
shot, facendo ricadere `boundary_confidences`, `reconcile` e lo splitter. Non serve: lo shot
uscente *include* la transizione e finisce a `j`, l'entrante parte a `j+1`. I range restano
contigui e coprono tutti i frame — nessuno dei tre consumatori e' stato toccato.

## Collaudo su *Rogue One*

`--split-mode none`, 6 minuti: **3204 shot**, 461 con transizione registrata, catalogo e UI
completi. Contratto verificato: contigui, copertura totale dei 192 701 frame.

**Ma il film non ha dissolvenze.** Delle 461 transizioni, **406 stanno sotto i 5 frame** — sono
stacchi con un frame di motion blur — e sopra i 10 frame ce ne sono **cinque in tutto**. E' lo
stesso muro di §5.3 (n=7 su SHOT): *Rogue One* e' montaggio serrato a stacchi netti.

**Conseguenza: su questo film OmniShotCut non servirebbe.** Il suo vantaggio vive sopra i 15
frame, dove qui non c'e' materiale.

## Cosa resta aperto

1. **OmniShotCut fuori dalla pipeline.** Misurato e complementare — la union porta il recall da
   0,215 a 0,534 — ma e' una dipendenza nuova, un modello da scaricare e una `reconcile` su
   range da scrivere. **E serve materiale con dissolvenze**, che *Rogue One* non ha.
2. **Il 25% degli shot ha confidenza sotto 0,2.** E' matematico (la confidenza *e'* la prob al
   taglio, e la soglia e' 0,05) e non e' un bug: sono gli shot che prima non vedevamo. Ma la UI
   li mostra come tutti gli altri, e un filtro per confidenza e' una riga di JS.
3. **`prove/annota_boundary.py` mai lanciato.** 40 giudizi ciechi, ~15 min: direbbe quanti dei
   219 shot sotto i 10 frame sono tagli veri, e chiuderebbe la questione AutoShot.
4. **AutoShot resta ambiguo**: su RAI trova piu' boundary di TransNet (0,836 contro 0,802), sulla
   delimitazione e' indistinguibile (0,083 contro 0,088).
