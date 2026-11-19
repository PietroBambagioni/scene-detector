# Piano — `fuoricampo`

Stato al 1 settembre 2026. Il metodo e le sue insidie stanno in `README.md`; qui c'è solo
cosa manca e in che ordine farlo.

**Dove siamo**: 390 segmenti, **198 minuti di film ritrovati su 214 (92%)**, 214 shot su 307,
**99% confermati** dalla riverifica a piena risoluzione. Il confronto gira su **cinque** parti
del girato: FC6 è uscito il 1 settembre, vedi sotto.

Le Fasi 1 e 2 sono fatte: la pagina di lavoro (`lavoro.py`) affianca i due filmati
sincronizzati, le descrizioni si correggono e ogni aggancio prende un verdetto, che
`applica_correzioni.py` riporta nel manifest e in `verdetti.json`.

E la precisione non è più una stima a occhio. `controllo.py` riverifica **tutti** i segmenti a
128×128 cercando zoom e posizione, in due minuti: mediana **0,827** contro **0,442** di 40
controlli casuali, e **387 su 390 (99%) stanno sopra il massimo dei controlli**. I 3 sotto
sono per metà veri (inquadratura molto più larga nel girato, o offset che deriva su un
segmento lungo) e per metà falsi — due dei quali con il fotogramma del film **quasi nero**.

Due questioni chiuse per strada:

- **FC1 allo 0% non era un difetto**: quei 80 minuti sono la *presentazione al festival* —
  il dibattito con Grifi e Sarchielli dopo la proiezione, tavolo, microfoni, pubblico,
  cartelli sul restauro in apertura, e nel parlato la Biennale di Venezia che paga la copia.
  Non contiene un fotogramma del film, e il metodo lo diceva correttamente. Dal 1 settembre
  le pagine lo chiamano col suo nome invece che «Fuori campo 1».
- **FC6 è fuori dal confronto**: non è girato, è un rimontaggio delle altre parti — 74 dei
  suoi 95 minuti (78%) si ritrovano in FC1..FC5, misurati con lo stesso metodo. I suoi 15
  segmenti erano il montato agganciato alla copia invece che all'originale; tolto FC6 quei
  pezzi ricompaiono nella parte da cui vengono e il totale resta 92%.
- **La griglia delle scale non taglia più gli ottimi**: zoom mediano 0,78, e con l'estensione a
  0,62 nessun ottimo cade sui bordi (era il sospetto lasciato aperto da `geometria.py`).

### Fatto il 1 settembre

- **`scartato.py` → «Il girato scartato.html»**, la pagina che risponde alla domanda opposta:
  9,1 ore su 12,5 di girato non entrano nel film, in 135 blocchi, una miniatura ogni due
  minuti. FC1 escluso dal conto perché non è materiale girato.
- **Provenienza in fondo alle pagine**, da `run.json` scritto dai passi mentre girano
  (`annota_passo`): data, soglie, parti, catena dei conteggi.
- **`confronta_run.py`**, il diff fra due run letto per shot invece che per segmento.

Restano dal brainstorming, in ordine di interesse: la **forma del montaggio** (i 390 punti
film×girato in uno scatter — solo 55 passi indietro su 386, ma con ritorni di ore), le
**riprese multiple** (93 minuti di girato usati da più di un segmento), l'**export dei tempi**
film↔girato, e i **verdetti** fermi a uno.

Le due richieste diventano tre fasi, perché la seconda apre la terza — che è dove sta il
guadagno vero.

---

## Fase 1 — confrontare i due filmati affiancati

Una **versione da lavoro** della pagina, che vive accanto ai video sul disco. Resta separata
da quella condivisibile: chi riceve il file autonomo continua a vedere solo i fotogrammi.

### 1.1 · La cartella e i symlink

I video stanno in due posti diversi (`Film/Anna.mp4` dentro il progetto, le parti
sul Desktop), e una pagina `file://` carica senza storie solo quello che le sta sotto. Non si
copiano 30 GB: `lavoro.py` crea `fuoricampo/lavoro/` con sei **symlink** e ci scrive
dentro la pagina, che li referenzia per path relativo — lo stesso schema di `clips/Film/`.

```
lavoro/
├── anna-lavoro.html
└── ANNA/Anna.mp4 · Fuori campo di Anna - 1.mp4 … - 5.mp4    (symlink, 0 byte)
```

Se i video si spostano, i symlink si rompono: `lavoro.py` li rifà, ed è l'unico posto dove i
path assoluti compaiono.

### 1.2 · I due player

In cima alla pagina un pannello `sticky` con due `<video preload="metadata">` affiancati,
film a sinistra e girato a destra. Ogni scheda prende un bottone **▶ confronta**, che:

1. punta i due `src` ai file giusti (il girato cambia file a seconda della parte);
2. imposta `currentTime` al centro dell'intersezione da un lato e al punto corrispondente
   dall'altro — è la stessa coppia di istanti delle due miniature, già calcolata da `per_shot`;
3. avvia entrambi.

**Sincronizzazione**: l'offset `girato − film` è costante dentro un segmento, quindi basta
tenerlo. Un `requestAnimationFrame` controlla lo scarto e riallinea quando supera 0,15 s —
i due decoder non avanzano allo stesso passo, e senza correzione divergono in un minuto.

**L'audio va scelto, non sommato**: due tracce insieme sono illeggibili. Tre stati (film /
girato / muto), il resto `muted`. Default sul film.

### 1.3 · I controlli che servono davvero

- **Regolazione fine dell'offset**, ±3 s con passo 0,1 s. I confini valgono ±1 s: senza
  questo, metà dei confronti parte sfasata e sembra un errore di aggancio quando non lo è.
- **Velocità** 0,5× / 1× / 2×, sui due insieme.
- **Salto ±5 s** su entrambi mantenendo l'offset.

Niente altro: non è un montatore.

**Verifica**: aprire dieci schede a caso e per ognuna vedere partire i due filmati sullo
stesso istante; dopo due minuti di riproduzione continua lo scarto deve restare sotto 0,2 s.

**Costo stimato**: `lavoro.py` una cinquantina di righe (riusa `costruisci` di `artifact.py`
con un parametro), più il pannello e ~80 righe di JS.

---

## Fase 2 — correzioni che tornano nel manifest

### 2.1 · Cosa si può correggere

Due cose diverse, che vanno in due posti diversi:

| cosa | dove appartiene | dove finisce |
|---|---|---|
| la **descrizione** dello shot (VLM, a volte sbagliata) | al film | `clips/Anna/manifest.json` |
| il **verdetto** sull'aggancio: giusto / sbagliato / incerto | al matching | `verdetti.json`, qui |

Tenerle insieme sarebbe comodo e sbagliato: la descrizione la usa anche il catalogo e
sopravvive a qualunque ritaratura delle soglie; il verdetto è un giudizio su *questo* run e
non ha senso dentro il manifest del film.

### 2.2 · Nella pagina

Un bottone **Correggi** in testa alla pagina mette le descrizioni in `contenteditable` e fa
comparire su ogni scheda tre bottoni per il verdetto. Un contatore dice quante modifiche
sono in sospeso, così non si chiude la finestra per sbaglio (`beforeunload` se non è vuoto).

**Esporta correzioni** scarica `correzioni.json`:

```json
{"generato": "2026-08-25T18:00:00", "segmenti": 390,
 "shot": {"178": {"descrizione": "…", "verdetto": "giusto"},
          "162": {"verdetto": "sbagliato", "nota": "sfocato, non verificabile"}}}
```

Il download funziona da `file://`. **Non** funzionerebbe dentro un artifact pubblicato, dove
i download avviati dalla pagina sono inerti — un motivo in più per tenere la versione di
lavoro separata.

La memoria del browser (`localStorage`) si usa solo come rete di sicurezza contro la chiusura
accidentale, mai come archivio: su un file aperto col doppio click Chrome la concede a
singhiozzo e Safari la nega. **L'archivio è il JSON esportato.**

### 2.3 · `applica_correzioni.py`

```
.venv/bin/python fuoricampo/applica_correzioni.py correzioni.json
```

- copia il manifest in `manifest.pre-correzioni.bak.json` prima di toccarlo (lo schema che il
  progetto usa già: `manifest.th005.bak.json`, `manifest.cleaned.json`);
- accoppia per **`start_frame`, non per `index`** — è la regola che il progetto ha già pagato
  due volte, e qui varrebbe uguale: basta un run a soglia diversa e le correzioni scivolano su
  shot che non descrivono, in silenzio. Se lo `start_frame` non c'è più, la correzione **non**
  si applica e viene elencata come non applicata;
- i verdetti li scrive in `verdetti.json`, accumulando fra sessioni invece di sovrascrivere.

**Verifica**: correggere tre descrizioni, esportare, applicare, rigenerare, e ritrovarle nella
pagina; rilanciare `match.py` a soglia diversa e controllare che le correzioni restino sugli
shot giusti e che quelle orfane siano segnalate invece che perse.

---

## Fase 3 — fatta

Tutte fatte, e il film ritrovato è passato dal 70% al **92%** in quattro passaggi:

| | copertura | come |
|---|---|---|
| match + soglie | 70% | diagonali nell'impronta |
| `estendi.py` | 86% | allungare i segmenti fin dove la verifica regge |
| `buchi.py` | 92% | **cercare** dentro gli shot a metà, senza fidarsi dell'offset |
| `scene.py` | 92,3% | offset più votato, per le scene lunghe e ferme |

Gli ultimi due passaggi hanno reso anche il risultato più interessante del progetto: dentro
una stessa inquadratura il montaggio ricuce pezzi presi da punti diversi del ciak.

### 3.0 · Il buio accoppia con tutto — fatto (`MIN_CONTRASTO = 15`)

`MIN_MOTO` ferma le immagini ferme ma non quelle **quasi nere**: due dei quattro falsi certi
hanno il fotogramma del film praticamente vuoto, agganciato a scene qualsiasi. Serve un minimo
di contrasto sul segmento, tarato come è stato tarato il moto — misurando prima i casi noti,
poi scegliendo la soglia.

### 3.1 · `controllo` dentro la pagina — fatto

Mostrarlo su ogni scheda e poter ordinare per quel valore porta i dubbi in cima invece di
farli cercare. Così il verdetto umano completa la misura invece di sostituirla.

### 3.2 · Gli shot mancanti — fatto (`recupero.py`)

Rilanciare **solo su quelli** con soglie basse e passare i candidati allo stesso
`controllo.py`: ora che costa 0,4 s a candidato, è la strada più economica per far salire il
70%.

## Il vecchio piano della Fase 3 (fatto)

Oggi la precisione è «12 su 12 su un campione». Con i verdetti raccolti mentre si guardano i
filmati — che è lavoro che faresti comunque — diventa un numero, e con un numero si smette di
tarare a occhio.

### 3.1 · Precisione per fascia, non in blocco

`precisione.py`: verdetti incrociati con correlazione, copertura, durata e scala. La domanda
non è «quanto sbaglia» ma **dove**: se i falsi si concentrano sotto una certa correlazione, la
soglia si sposta lì e si guadagna precisione senza perdere niente. Bastano ~60 verdetti per
avere fasce sensate.

### 3.2 · La griglia delle scale è probabilmente tagliata al bordo

In `geometria.py` diversi ottimi cadevano **esattamente su 0,70**, cioè sul limite inferiore
della griglia: segno che l'ottimo vero sta più in là. Aggiungere 0,62 e 0,66 costa un matmul
in più (secondi) e nessuna ridecodifica, perché le scale si generano in RAM. Se i verdetti
confermano match veri sulla scala minima, è il primo esperimento da fare.

### 3.3 · I 134 shot non ritrovati

Non è detto che manchino dal girato: possono stare sotto soglia o fuori dalla griglia delle
scale. Rilanciare **solo su quelli** con soglie basse e verdetto a occhio sui candidati. È
qui che il player della Fase 1 si ripaga: verificare venti candidati deboli guardando i
filmati costa minuti, non ore.

### 3.4 · I confini

Oggi valgono ±1 s (campionamento 0,5 s + tolleranza del voting). Se dopo la Fase 1 si vede
che partono spesso sfasati, si raffinano *solo sui segmenti confermati*, cercando l'offset
esatto a piena risoluzione attorno ai bordi. Lavoro inutile finché i verdetti non dicono che
serve — e il regolatore fine della 1.3 lo rende sopportabile nel frattempo.

---

## Rifiniture della pagina (fatte)

Nate quasi tutte guardandola in uso, non progettandola:

- **Tre tempi, e in testa ne resta uno.** Su una scheda convivono l'intervallo dello *shot*,
  il *pezzo* ritrovato e l'istante del *fotogramma*. Mostrare shot e fotogramma insieme
  sembrava una contraddizione: dal 2 settembre in testa c'è solo l'istante del fotogramma, e
  il pezzo sta nella riga che dice anche da quanti pezzi è coperto lo shot.
- **La trascrizione in una tendina**, con il numero di parole. Duecento parole per scheda
  seppellivano i fotogrammi; in correzione le tendine si aprono da sé.
- **Caselle vuote dove il testo manca** (1 descrizione, 22 trascrizioni): un trattino non si
  può riempire.
- **Due ricerche separate**, descrizioni e parlato, combinabili.
- **Le tacche del non ritrovato cliccabili**, che portano al fotogramma in fondo.
- **Stop alla fine dello shot**, senza coda.
- **Due famiglie di colore**: freddi il ritrovato, caldi il mancante — con i caldi scuriti per
  il tema chiaro, dove il giallo era a 1,7× di contrasto.

## Rischi

- **I symlink si rompono** se i video si spostano o il Desktop cambia nome. `lavoro.py` va
  rilanciato: è l'unico punto dove stanno i path assoluti.
- **Safari con `file://`** è più restrittivo di Chrome su sottorisorse e memoria locale. La
  pagina di lavoro si prova su Chrome; quella condivisibile non ha il problema perché non
  carica niente.
- **Mai servire la pagina di lavoro con `python -m http.server`**: non implementa `Range`,
  quindi ogni salto a un minutaggio fa ripartire il video da zero e sembra un bug della
  pagina. Doppio click, sempre. (È già nei gotcha del `CLAUDE.md`.)
- **Le correzioni vivono solo nel JSON esportato** finché non si lancia
  `applica_correzioni.py`. Il contatore in pagina serve a ricordarlo.

## Deciso: non si fa

- **Ritagliare le clip dei 390 segmenti.** Ore di encoding e diversi GB per ottenere quello
  che due player affiancati danno senza copiare un byte. Si riapre solo se serve mandare i
  confronti a chi non ha i video.
- **Rimettere l'audio nel matching.** Misurato: 289 segmenti, tutti falsi. Il perché è in
  `README.md` — l'audio del montato è rimissato e a 32 bande mel il parlato correla con sé
  stesso ovunque.
- **Un server locale per la pagina.** Vedi il gotcha su `Range`.
- **Salvare le descrizioni corrette dentro `verdetti.json`** (o i verdetti dentro il
  manifest). Sono due cose con due vite diverse: mescolarle significa perderne una alla
  prima ritaratura.
