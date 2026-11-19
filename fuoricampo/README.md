# Anna nel *Fuori campo* — cosa del montato sta nel girato

Il film (`Film/Anna.mp4`, 3h34) e le parti del *Fuori campo di Anna* trasmesse da Fuori
Orario sono due generazioni dello stesso materiale. Qui si cerca, per ogni pezzo del montato,
dove sta nel girato.

**Risultato**: 390 segmenti, **198 minuti di film ritrovati su 214 (92%)**, 214 shot su 307.

Questo file è il verbale: i numeri, le soglie, le cose provate e buttate. Se cerchi il
racconto di **come** si è arrivati fin qui, in italiano e senza gergo, sta in
[`Come è stato fatto.md`](<Come è stato fatto.md>) — e in PDF accanto, da rifare con
`./rifai-pdf.sh` quando il markdown cambia.

Precisione **misurata**, non stimata: `controllo.py` riprende ogni segmento a 128×128 cercando
zoom e posizione — mediana **0,827** contro **0,442** di quaranta accoppiamenti casuali, e
**387 su 390 (99%) sopra il massimo dei controlli**. Due minuti per tutto il film.

### Le parti in gioco sono cinque, non sei

Le trasmesse sono sei, ma solo cinque sono materiale da cercare (13h53, `PARTI` in
`impronta.py`):

- **FC6 è escluso**: non è girato, è un rimontaggio delle altre parti. Misurato con lo stesso
  metodo e le stesse soglie, usando FC6 come «film» contro FC1..FC5: **74 dei suoi 95 minuti
  (78%) stanno già nelle altre parti**. Tenendolo, il montato finiva agganciato alla copia
  invece che all'originale — 15 segmenti su 391, di cui solo l'11% coperto anche altrove,
  perché il match è greedy e una volta trovato un pezzo in FC6 non lo cercava più altrove.
  Toltolo, quei pezzi ricompaiono nella parte da cui vengono (FC2 passa da 94 a 108 segmenti)
  e il totale non si muove: 92% prima, 92% dopo.
- **FC1 resta ma non è girato**: è la **presentazione al festival** — il dibattito con Grifi e
  Sarchielli dopo la proiezione, tavolo, microfoni e pubblico, con in apertura i cartelli sul
  restauro. Nel parlato si sente da dove viene: «la copia è stata pagata dalla Biennale di
  Venezia», «il risultato tecnico a cui abbiamo assistito questa sera durante la proiezione».
  Il suo 0% è un risultato, non un buco, e nelle pagine si chiama col suo nome invece che
  «Fuori campo 1» — vedi `etichetta` in `timeline.py`.

### Le scene lunghe e ferme, e dove il recupero si ferma

`match.py` cerca **diagonali**: corse in cui il girato avanza insieme al film. Su un primo
piano di cinque minuti che si muove poco, però, ogni fotogramma somiglia a decine di punti del
girato, il candidato migliore salta di qua e di là e la diagonale non si forma — anche col 54%
dei fotogrammi sopra 0,75, come nello shot 110. `scene.py` vota diversamente: prende tutti i
candidati dello shot e tiene l'**offset più votato**, perché non conta che i match siano
ordinati, conta che siano d'accordo.

Resa: poca. Sette proposte, **cinque vere** guardandole — 71% di precisione contro il 98% del
resto — per meno di un minuto. Sono entrate solo le cinque verificate a occhio: applicare
tutto avrebbe peggiorato la qualità del risultato per un guadagno trascurabile, e questo è il
punto in cui conviene fermarsi.

Il cartello di testa, intanto, era **tornato** agganciato alla sua targa con 0,87 di
controllo: `scene.py` filtrava il contrasto ma non il moto. Cambiare *come* si vota non rende
verificabile ciò che non lo è — su un'immagine ferma l'accordo fra candidati è accordo su
niente, esattamente come la diagonale era diagonale su niente.

### Dentro uno stesso shot, il girato salta

`estendi.py` allunga un segmento **tenendo fermo il suo offset**, e lì si ferma. Ma i pezzi
scoperti dentro shot già agganciati raccontano un'altra storia: cercandoli senza vincolo di
offset (`buchi.py`), **35 dei 49 confermati stanno in un punto diverso del girato** — spesso
nella stessa parte, qualche decina di secondi più in là.

Non è un difetto del metodo: è il montaggio. Dentro quella che il detector vede come una sola
inquadratura, Grifi ha ricucito materiale preso da momenti diversi del ciak. Cercare invece di
allungare vale **+12,7 minuti, dall'86% al 92%**.

La regola che ne esce: *l'offset del segmento vicino è un'ipotesi, non un dato*. Va bene per
prolungare, non per riempire un buco — e quale delle due serva lo dicono i candidati, non
l'intuizione.

### Il rovescio: nove ore che non entrano

`artifact.py` risponde sempre alla stessa domanda — dato un pezzo di montato, dove sta nel
girato. `scartato.py` gira la domanda: delle **12 ore e 32** di girato trasmesso, **9,1 non
compaiono nel film** (72%), in 135 blocchi da mezzo minuto in su. Il più lungo è l'ora e
mezza iniziale di FC5.

Il dato era già tutto in `segmenti-video.json` — è il **complemento** degli intervalli usati,
parte per parte — ma esisteva solo come spazio vuoto fra due tacche, cioè come niente. Due
scelte lo rendono guardabile:

- **una miniatura ogni due minuti di blocco**, fino a dieci. Un blocco di novanta minuti
  descritto da un fotogramma solo non si può giudicare, ed è il caso che conta di più: i
  blocchi lunghi sono il 54% del non usato.
- **FC1 fuori dal conto.** È la presentazione al festival, non girato: comparirebbe come il
  blocco più lungo di tutti e sposterebbe la cifra in testa di un'ora e venti. Una parte che
  non è materiale non è materiale *scartato*.

Sotto i trenta secondi non si conta: quello non è un pezzo lasciato fuori, è lo stacco fra
due riusi vicini.

### Da che run viene questo file

Le pagine girano per posta e sopravvivono al codice che le ha fatte: in due giorni qui è
cambiato il numero di parti del girato, e due file identici nell'aspetto raccontavano numeri
diversi. In fondo a ogni pagina ora c'è la riga di provenienza — data, soglie, parti, la
catena dei passi con i loro conteggi.

I dati vengono da `run.json`, che **scrivono i passi mentre girano** (`annota_passo` in
`timeline.py`), non il generatore leggendo il sorgente al momento di disegnare la pagina: le
soglie in `match.py` si toccano, e una pagina che dichiarasse i parametri *di adesso* li
direbbe sbagliati proprio quando servono, cioè quando il file è già in giro e nessuno può
più risalire a com'era il codice. Un `match.py --video` azzera il registro, perché invalida i
passi che lo seguivano.

### Confrontare due run

`confronta_run.py PRIMA.json [DOPO.json]`. Il confronto è **per shot del film**, non per
segmento: i segmenti si spezzano e si fondono fra un run e l'altro — `estendi` allunga,
`buchi` aggiunge — quindi contarli dà una differenza che non vuol dire niente. Lo shot invece
è la stessa cosa nei due run.

Serve perché **un totale identico può nascondere un rimescolamento completo**: togliendo FC6
la copertura è rimasta al 92% e sembrava non fosse successo nulla, mentre sei shot avevano
cambiato parte (FC6 → FC2), uno si era agganciato e uno era rimasto senza. Quell'ultimo,
lo shot 139, stava al 100% su FC6 e in FC1..FC5 non si ritrova: è materiale che nel girato
trasmesso esiste solo dentro il rimontaggio.

### La matita: riscrivere i testi della pagina

In alto a destra, fissa, una **✎** che rende modificabile ogni scritta — titoli, sommario,
guide, etichette delle barre, numeri, didascalie, filtri, piè di pagina. Serve a rivedere le
parole dove si vedono, invece che nel generatore alla cieca. Accanto compaiono, solo quando
c'è qualcosa da salvare, **↓ n** (scarica `testi.json` con `originale`/`nuovo` di ogni
modifica) e **↺** (rimette tutto com'era).

Tre cose non ovvie:

- **«Tutte le scritte» è una domanda su chi porta il testo, non sulla disposizione.** Il primo
  criterio guardava il `display` dei figli per capire se un elemento fosse una foglia — ma
  dentro un contenitore `flex` i figli vengono blocchificati, quindi il pallino colorato della
  legenda risultava «blocco» e la voce restava fuori. Ora la regola è: ha testo proprio, o
  nessun figlio che porti testo. Il CSS non c'entra.
- **In un `<button>` il cursore non ci si posa.** Un bottone è un comando: il clic gli dà il
  fuoco come controllo. `contenteditable` sul bottone accetta le modifiche fatte da codice,
  ma dipendere da quello sarebbe fragile — così mentre si scrive i chip e le voci della
  legenda vengono **sostituiti** da uno `<span>` con le stesse classi, e alla chiusura tornano
  i bottoni veri, coi loro gestori intatti e il testo nuovo. I glifi dei comandi (▶ ✓ ✗ ?) no:
  quelli non sono testo d'autore.
- **La chiave è il testo originale, non la posizione.** In `localStorage` una modifica si
  ritrova solo se la frase di partenza è ancora quella: se un run nuovo riscrive una guida, la
  correzione vecchia non si applica invece di finire su una frase che non è la sua. Stessa
  regola di `merge_prior` e di `applica_correzioni.py`, che accoppiano per `start_frame` e mai
  per indice.

E mentre si scrive i clic dentro la pagina vengono fermati **in cattura**, con
`stopPropagation` e non `preventDefault`: senza, premere «FC3» filtrerebbe invece di posare il
cursore; con `preventDefault`, non si poserebbe nemmeno.

### Correzioni: descrizione **e** parlato

Sono modificabili entrambe, e finiscono nello stesso JSON: le descrizioni le scrive un modello
visivo, le trascrizioni un riconoscitore automatico, e sbagliano tutte e due. Le ricerche sono
**due campi separati** — «cerca nelle descrizioni» e «cerca nel parlato» — perché cercare una
parola detta è un'altra cosa dal cercare una parola scritta *su* ciò che si vede, e i due
filtri si combinano.

### Due famiglie di colore che non si toccano

Il **mancante** sta nei caldi: rosso le scene vere, arancione i cartelli, giallo i neri. Le sei
parti del girato tengono i colori originali che non sono né gialli né rossi — ciano, verde,
magenta, blu — più verde-acqua e viola nei due posti lasciati liberi. Prima il rosso delle
scene mancanti era anche il colore di FC5 e i cartelli erano grigi su fondo grigio: due sistemi
di significato che si contendevano la stessa tinta, in una pagina dove il colore *è*
l'informazione.

I caldi hanno dovuto essere scuriti per il tema chiaro: sul fondo chiaro il giallo stava a
**1,7×** di contrasto, cioè invisibile. Ora tutte le tinte stanno sopra 3:1 in entrambi i temi
— che per un elemento grafico è la soglia sotto la quale semplicemente non lo si vede.

### La barra del non ritrovato

Le tacche sono **cliccabili**: portano al fotogramma corrispondente in fondo alla pagina, così
si vede *che cosa* manca in quel punto senza cercarlo a mano fra novantatré miniature.

Anche i tre quadratini della legenda sono bottoni: premendone uno la barra mostra **solo**
quel tipo di buco, e ripremendolo si torna a vederli tutti. Serve perché a densità piena i
tre colori si mescolano e non si legge dove cadono i cartelli — che sono l'unica famiglia con
una distribuzione sua, tutta all'inizio e alla fine. Non c'è un bottone «tutti» come fra i
chip: è il quadratino acceso a spegnersi, altrimenti sarebbe un filtro che non si sa più
togliere.

Sotto quella del film c'è una seconda barra con i **buchi**, colorati per tipo: rosso le scene
vere, grigio i cartelli, scuro i neri. Senza, l'assenza è solo spazio vuoto e non si distingue
un buco che si potrebbe inseguire da uno che nel girato non può esistere. La barra copre sia
gli shot mai ritrovati sia le porzioni scoperte **dentro** shot agganciati, che sono la metà
del mancante e altrimenti resterebbero invisibili.

### Riordinare sposta i nodi, e la madre non è quella che sembra

`dubbi in cima` riappende le schede ordinate per punteggio di verifica. Le riappendeva a
`schede[0].parentNode`, che era `.foglio`, cioè **tutta la pagina**: ogni riordino le spediva
in fondo, sotto la sezione degli assenti e sotto il piè di pagina. Da fuori non sembrava
affatto un problema di ordinamento — sembrava che il bottone mettesse in cima la sezione
sbagliata, e che il secondo clic non facesse niente (le schede si riordinavano davvero, ma
sempre laggiù, fuori dallo schermo). Ora le schede stanno in un `.schede` loro.

La regola: **`appendChild` in un ciclo di riordino ha bisogno di un contenitore che contenga
*solo* le cose da riordinare.** Se la madre contiene anche altro, l'ordinamento funziona e il
sintomo si presenta come un problema di layout.

### La sezione «Quello che il girato non contiene»

I 93 shot mai ritrovati non stanno in una lista richiudibile ma in una sezione con le loro
miniature, divisi per **che cosa sono**: cartelli, neri, scene vere. Serve a rendere
giudicabile a occhio l'unica cifra che altrimenti resterebbe opaca — il non trovato — e si
vede subito che i cartelli sono cartelli.

Accanto a `dubbi in cima` c'è **`non trovati in cima`**, che porta quella sezione sopra le
schede. Non è un ordinamento come l'altro bottone ed è giusto che non lo sia: uno shot senza
aggancio non ha una scheda, perché non c'è un girato da metterci accanto. La sezione si sposta
davanti a `.schede` e torna dietro `.vuoto`, che è l'unico elemento della pagina che non si
muove mai — un'ancora vale più di una posizione ricordata.

### Cosa manca davvero, dei 30 minuti che restano

I 16 minuti scoperti si dividono in due metà molto diverse: **7,3 min (45%) non possono
esistere nel girato** — 5,4 di cartelli e 1,9 di neri — e **8,7 min (55%) sono scene vere, in
linea di principio ritrovabili**. Di quegli 8,7, sei minuti e mezzo stanno in 13 shot mai
agganciati e il resto dentro 20 shot agganciati solo in parte: dopo `buchi.py` la riserva
dentro gli shot agganciati non è più quella grossa che era.

Il conto va fatto sui **minuti scoperti**, non sugli shot senza aggancio: sono due tagli
diversi dello stesso dato e danno cifre diverse (7,3 contro 5,9 di «non può esistere»), perché
un cartello può stare dentro uno shot che per il resto è agganciato.

Guardati a campione, gli shot senza aggancio non sono un difetto del metodo: **39 sono
fotogrammi neri** e **41 sono cartelli** — «25 FEBBRAIO 1972 · MASSIMO INCONTRA ANNA A PIAZZA
NAVONA», «LA DOCCIA, I PIDOCCHI», «FLASH BACK» — che Grifi ha creato **in montaggio** e che nel
girato non possono esistere, come la presentazione al festival di FC1. Le scene vere non
ritrovate sono **13, per 6,6 minuti**: il 3,1% del film.

### Estendere, non cercare

Trentacinque minuti stavano **dentro** shot già agganciati: una corsa si ferma appena la
somiglianza scende per qualche campione, anche se nel girato la ripresa continua. Lì non serve
cercare — il segmento accanto dà già l'offset — serve allungare finché la verifica regge
(`estendi.py`): **+22 minuti, dal 76% all'86%**, con i bordi nuovi misurati a 0,819 contro
0,442 dei casuali.

Due trappole, che sono la stessa trappola:

- **La soglia dei casuali non serve a estendere.** Appena fuori da un segmento la verifica dà
  0,674 di mediana — dentro una ripresa continua i fotogrammi vicini si somigliano tutti —
  quindi con 0,648 l'estensione non si ferma mai. Riconoscere e prolungare sono due problemi
  diversi e vogliono due soglie diverse (qui 0,76, in mezzo fra 0,835 e 0,674).
- **Dopo un'estensione la somma delle durate non è più la copertura.** I segmenti vicini si
  allungano l'uno verso l'altro e si sovrappongono: la somma diceva 322 minuti su un film che
  ne dura 214. Il numero impossibile ha salvato la misura — va presa l'**unione** degli
  intervalli (`copertura`), e l'estrapolazione da un campione sparso non vale, perché lì le
  sovrapposizioni non ci sono.

```
impronta.py       video  -> [N, 48, 48] uint8 a 2 campioni/s        (~15 min per le 19 ore)
impronta_audio.py audio  -> [N, 256]    a 2 campioni/s              (~1 min)   — scartato, vedi sotto
match.py --video         -> segmenti-video.json                     (~2 min su MPS)
soglie.py                -> la curva soglie/minuti, e rigenera il json a soglie diverse
timeline.py --miniature  -> timeline.html + relazione.md      (usa thumbs/ sul disco)
scartato.py --miniature  -> "Il girato scartato.html"     il rovescio: le nove ore di
                            girato che nel film non entrano mai
confronta_run.py A [B]   -> che cosa è cambiato fra due run, shot per shot
artifact.py --offline    -> "Anna nel Fuori campo.html"       un file solo, 2,9 MB:
                            fotogrammi e font dentro, zero richieste di rete, si apre
                            col doppio click e si manda via mail o su chiavetta
lavoro.py                -> lavoro/anna-lavoro.html          la versione da lavoro: i due
                            filmati affiancati e sincronizzati, le descrizioni correggibili
                            e il verdetto su ogni aggancio. Non condivisibile: vive di
                            symlink ai video. Da aprire col doppio click, su Chrome.
applica_correzioni.py    -> correzioni.json -> manifest + verdetti.json
controllo.py             riverifica ogni segmento a 128×128 -> controllo.json  (~2 min)
recupero.py --applica    ricerca a soglie basse sugli shot scoperti, tiene solo ciò che il
                         controllo conferma. Da rilanciare dopo ogni match.py --video
conversazione.py         il transcript JSONL della sessione -> CONVERSAZIONE.md
serve.py                 server locale con Range: serve SOLO a pilotare la pagina da
                         un'estensione del browser, che i file:// non li apre. Per
                         guardarla basta il doppio click.
verifica.py · geometria.py · sonda.py   banchi di misura, uno per ogni ipotesi provata
```

## Il metodo

Un vettore ogni mezzo secondo per entrambe le sorgenti, normalizzato a media 0 e norma 1
(il prodotto scalare è la correlazione di Pearson); un matmul su MPS confronta i 25 659
istanti del film con i 111 353 del girato in 1,4 s. Poi il voting: **un match isolato non
conta**, conta una corsa di istanti in cui il girato avanza di mezzo secondo ogni volta che
il film avanza di mezzo secondo. Su materiale tutto in bianco e nero, sempre nella stessa
stanza, è l'unica cosa che distingue un riuso da una coincidenza.

## Le quattro cose che sembravano vere e non lo erano

**1. «Il crop è lo stesso per tutto il girato.»** No: FC2..FC5 hanno l'immagine larga 1151 px,
FC1 1057, FC6 1044. Con un crop unico l'impronta del girato inquadra una porzione diversa da
quella del film e il match crolla. `cropdetect` da solo non basta — legge un frame alla volta
e prende per barra nera qualsiasi scena scura ai bordi: va misurato il 75° percentile della
luminanza per colonna su qualche centinaio di frame.

**2. «Due frame simili bastano.»** No: lo z-score porta a norma 1 anche un frame che non
contiene niente. Una parete grigia con un filo di luce in alto diventa un vettore forte quanto
un primo piano e correla 0,93 con qualunque inquadratura chiara-sopra-scura-sotto. Il 90% dei
primi falsi positivi era questo. Si toglie proiettando via il gradiente lineare
(`smonta_gradiente`) e buttando i frame che erano *solo* gradiente.

**3. «Meglio l'audio: è presa diretta.»** Sembrava ovvio — l'audio non ha crop, logo, banner né
grading — e ha dato **289 segmenti tutti falsi**. Due motivi. A 32 bande mel, parlato registrato
nella stessa stanza correla 0,87 con qualunque altro parlato nella stessa stanza: la mediana
del *miglior* candidato era 0,87, cioè l'impronta non distingueva niente. E l'audio del montato
è rimissato: sui match che l'occhio conferma veri, la forma d'onda non si aggancia comunque.

**4. «La correlazione della forma d'onda è il giudice.»** Solo su finestre corte. Due copie
passate per catene diverse non hanno la stessa velocità al campione: **basta lo 0,02% di
scarto** perché su 30 s le due forme d'onda si sfasino di 6 ms e la correlazione crolli da
1,000 a 0,085 — indistinguibile dal rumore. Su finestre da 2 s lo stesso drift vale 0,4 ms e
la correlazione regge a 0,38. I primi «0 su 25» non provavano l'assenza di corrispondenze,
provavano che il giudice era rotto. **Il video non ha questo problema**: confronta fotogrammi
singoli, non finestre, e il drift lo assorbe la tolleranza del voting.

## La geometria: non ce n'è una sola

I primi match veri correlavano 0,80 dove due copie della stessa immagine dovrebbero stare a
0,98. Guardandoli affiancati si vede perché: **il girato mostra più campo, il montato è
ricadrato più stretto**. Ma cercando lo zoom che allinea dieci coppie confermate
(`geometria.py`, tempo e geometria cercati *insieme* — a tempo sbagliato la stima è rumore)
viene fuori che non esiste un valore unico: **0,70 ÷ 0,96, diverso da ripresa a ripresa**.
Coerente con come *Anna* è stato fatto: girato in video ½", poi vidigrafato rifilmando un
monitor, un'inquadratura alla volta.

Da qui il multi-scala: si estrae a 48×48 una volta sola e si generano cinque riduzioni a
24×24 in RAM (`riduci`), invece di ridecodificare 19 ore per ogni scala. Il recall passa da
**6,5% a 70,5%** e la correlazione mediana delle coppie confermate da 0,50 a 0,83.

## Le soglie

`TH_FRAME=0,70 · TH_SEG=0,80 · MIN_LEN=6` (3 s). La curva sta in `soglie.py`: alzando a
0,85/0,88 si scende a 50 min (23%), a 0,92/0,94 a 3 min (1,3%). La precisione a occhio è la
stessa (9/10) alla soglia bassa e a quella alta, quindi si tiene la bassa. **Il numero di
minuti ritrovati da solo non dice niente**: sale sempre abbassando le soglie, e va letto
insieme a un campione guardato a occhio.

## I tre difetti trovati rileggendo i risultati

Partiti da un errore segnalato a occhio — il cartello «si consiglia la visione a un pubblico
adulto» agganciato a una **targa incisa** nel girato — ne sono venuti fuori tre, e il più
grave non era quello.

**Le miniature non erano la coppia vera.** Si prendeva il fotogramma al centro dello *shot* e
quello al centro della *porzione di girato*. Con una copertura parziale il centro dello shot
cade fuori dalla parte coperta, quindi la pagina mostrava due immagini che non si
corrispondono **anche quando il match era giusto**: il difetto peggiore, perché toglieva a
chi guarda la possibilità di verificare tutto il resto. Ora entrambi i fotogrammi si prendono
al centro dell'**intersezione**, che per costruzione è lo stesso istante.

**Gli sfioramenti di confine.** `per_shot` accettava qualsiasi sovrapposizione maggiore di
zero: 188 agganci su 420 stavano sotto il 15% di copertura, alcuni di 0,0 s, e **40 shot
risultavano ritrovati** solo perché un segmento vicino ne sfiorava il bordo. Ora servono
almeno 1 s e il 10% dello shot. È da qui che i 222 shot sono diventati 173: il numero di
prima contava gli sfioramenti.

**Le immagini ferme.** Questa è la causa del caso segnalato, ed è strutturale: **su un
fotogramma statico la coerenza temporale non dimostra niente**. Una corsa di sei fotogrammi
identici «avanza in parallelo» a qualunque altra corsa di sei fotogrammi identici, quindi il
voting — l'unica difesa contro le coincidenze — approvava senza aver verificato nulla. A
24×24 un cartello e una targa sono lo stesso oggetto: un rettangolo chiaro su fondo scuro.
Ora un segmento vale solo se il film **si muove** al suo interno (`MIN_MOTO`): cartelli e
titoli di coda stanno a 0,000÷0,003, le inquadrature vere a 0,018÷0,318.

*Ipotesi provata e buttata*: che i cartelli si riconoscessero dalla concentrazione
dell'energia (kurtosi del vettore). Non separa — il cartello sta a 2,13 e la targa a 1,68,
**sotto** la mediana del film (2,75), in mezzo alle inquadrature vere (1,87÷3,26). Dopo la
riduzione a 24×24 un cartello non è sparso, è un blocco esteso.

## La pagina da lavoro

`lavoro.py` crea `lavoro/ANNA/` con sei **symlink** (non copia 30 GB) e ci scrive accanto
la pagina. È l'unico file dove stanno i path assoluti del materiale: se i video si spostano,
si rilancia solo quello.

**L'audio del girato è più basso di quello del film**: −33/−36 dB contro −27, cioè circa un
terzo dell'ampiezza. Premendo «girato» si sente, ma così sotto da sembrare muto — e un
`<video>` non amplifica oltre il suo volume nominale. Da qui il guadagno ×3 via Web Audio,
costruito al primo click (un `AudioContext` creato prima di un gesto dell'utente nasce
sospeso) e con il ripiego sul volume nativo se il browser non lo permette.

Sul banco di confronto: **▶ parti insieme** (o la barra spaziatrice) avvia i due filmati sullo
stesso istante — gli stessi due istanti delle miniature, non ricalcolati. L'audio si sceglie,
non si somma. Il comando che serve più di quanto sembri è **scarto**: i confini valgono ±1 s,
e senza la regolazione fine metà dei confronti parte sfasata e *sembra* un aggancio sbagliato
quando non lo è.

### Il riallineamento che si mangiava da solo

I due decoder non avanzano allo stesso passo e vanno riallineati. Riallineare con un **salto**
però costringe il decoder a ripartire dal keyframe: il girato perde terreno *proprio perché è
stato riallineato*, sfora di nuovo, salta di nuovo. Misurato su una registrazione dello
schermo: **16 salti in 16 secondi**, cioè scatti continui, con l'immagine peraltro accoppiata
correttamente — era la riproduzione a essere rotta, non il match.

Quattro cose insieme lo risolvono, e nessuna basta da sola:

- il **salto è l'ultima risorsa** (soglia 2 s, non 0,5): un secondo di disallineamento si
  sopporta guardando, un video a scatti no;
- il recupero è **una variazione di velocità** del girato, ±12% — con ±4% non recuperava mai e
  finiva comunque nel salto;
- la velocità si tocca **due volte al secondo**, non a ogni fotogramma: il ciclo gira a 60 Hz
  e cambiare `playbackRate` 60 volte al secondo produce da solo gli artefatti che si voleva
  togliere;
- mentre il girato **carica o cerca** (`readyState < 3`, `seeking`) non lo si tocca:
  intervenire lì lo manda in stallo, che è l'altra metà del circolo vizioso.

Il selettore di velocità agisce solo sul film, perché quella del girato la governa il
riallineamento. Il contatore dei salti sta accanto allo scarto: se resta basso l'immagine
scorre; se risale, il problema non è più la sincronia ma il carico di decodifica.

### La fine del confronto

Alla fine del pezzo accoppiato i due filmati **si fermano**, con una fascia che lo dice. Il
confronto finisce lì, e lasciar scorrere il film oltre serve solo a far perdere il segno.

### La trascrizione sta in una tendina

Le trascrizioni arrivano a duecento parole e riempivano schermate intere fra una scheda e
l'altra, seppellendo quello che si è venuti a vedere — i due fotogrammi e i minutaggi. Ora
stanno dietro una riga richiudibile che ne dichiara la lunghezza («trascrizione · 223 parole»),
e chi vuole leggerle apre.

Due dettagli che la rendono usabile: in modalità correzione **le tendine si aprono tutte**,
perché correggere un testo che non si vede non ha senso; uscendo restano aperte solo quelle
toccate. E la ricerca nel parlato continua a funzionare sul testo chiuso, perché filtra su un
attributo della scheda, non sul testo visibile.

### Dove non c'è testo, c'è comunque dove scriverlo

Uno shot senza descrizione o senza trascrizione mostrava un trattino o niente affatto — cioè
nessun posto in cui scrivere. Ora sono **caselle vuote** come le altre (1 descrizione e 22
trascrizioni), con un segnaposto tenue che in lettura dice «nessuna descrizione» e in
correzione «scrivi la trascrizione…». Il segnaposto è un pseudo-elemento CSS, quindi non
finisce mai nel testo esportato.

### Tre tempi, e in testa alla scheda ne resta uno

Su una scheda convivono tre istanti diversi, tutti legittimi:

- l'**intervallo dello shot** nel montaggio — l'inquadratura fra due stacchi, 0:01:35 → 0:03:02;
- il **pezzo ritrovato**, che può essere più corto — 0:02:10–0:02:55;
- il **fotogramma mostrato**, al centro *del pezzo* e non dello shot — 0:02:33.

Accanto al nome dello shot stava il **primo**, e leggere «Shot 005 0:01:35 → 0:03:02» sopra
«fotogramma a 0:02:33» sembrava una contraddizione: sono due orologi diversi solo per chi già
sa che il fotogramma si prende dentro il pezzo. Ora in testa c'è **solo l'istante del
fotogramma**, cioè lo stesso numero della didascalia sotto la miniatura; l'intervallo dello
shot non si mostra più e il pezzo resta scritto per esteso nella riga «il fotogramma viene dal
pezzo…», che compare quando la copertura è parziale e dice anche da quanti pezzi è coperto lo
shot — è così che uno shot può risultare coperto al 93% mentre il pezzo mostrato ne copre metà.

L'intervallo intero dello shot resta in `timeline.html`, che è la pagina di servizio e non
quella che si manda in giro.

*Provata e buttata*: una seconda coppia di fotogrammi presa alla fine del pezzo, per vedere
se l'aggancio regge fino al bordo. Quattro immagini per scheda rendono la pagina un mosaico
e la portano a 5,9 MB; la fine del pezzo la dice il minutaggio, e per guardarla davvero c'è
il banco a due filmati.

### Via «ricompare anche in»

La riga elencava gli **altri pezzi** che coprono lo stesso shot, e la parola prometteva una
cosa che quasi mai era vera. Misurato: dei 90 shot coperti da più di un pezzo, gli altri
pezzi stanno **131 volte allo stesso offset** — cioè sono la stessa ripresa continua,
spezzata dall'algoritmo quando la corsa si è interrotta e `estendi`/`buchi` l'hanno ricucita
— e solo **36 a un offset diverso**, che sono le ricomparse vere. Una riga giusta il 22%
delle volte non è un'informazione, e il numero di pezzi lo dice già la riga sopra («lo shot
è coperto da 4 pezzi»).

Verificato nel browser, non solo a mente: due filmati partiti insieme sullo stesso
fotogramma, **scarto +0,02÷0,03 s dopo un minuto** di riproduzione continua, verdetto dato,
esportato, applicato. Il ciclo intero regge.

Le correzioni vivono nel JSON esportato, non nel browser: `localStorage` è solo una rete di
sicurezza contro la chiusura per sbaglio (su `file://` Chrome lo concede a singhiozzo e
Safari lo nega). `applica_correzioni.py` accoppia per **`start_frame`, mai per indice**, e
quello che non trova più lo **elenca invece di applicarlo altrove** — vale sia per le
descrizioni sia per i verdetti, che altrimenti falserebbero il conteggio della precisione,
cioè l'unica cosa per cui esistono.

### Il permesso a riprodurre si perde fuori dallo stack del click

Al primo «confronta» i filmati non partivano, ma premendo poi «parti insieme» sì. Non era il
caricamento: è la policy di autoplay. Un `play()` chiamato dentro il callback di
`loadedmetadata` non è più considerato avviato dall'utente, e il browser lo blocca **in
silenzio** — nessun errore in console, solo due riquadri fermi. Va chiesto subito, dentro il
gestore del click, e i tempi si sistemano quando i metadati arrivano.

### Il bug del doppio regime delle graffe

Il documento esce da una f-string, dove le graffe vanno **raddoppiate**; `lavoro_js` è una
stringa normale, dove vanno **singole**. Due patch scritti con la convenzione sbagliata sono
passati senza errore e senza effetto: la prima volta hanno prodotto JavaScript invalido (e la
pagina è morta tutta), la seconda hanno semplicemente mancato il testo da sostituire — i due
campi di ricerca c'erano ma **senza il loro gestore**, e cercare non filtrava niente.
Il generatore controlla la sintassi, non l'efficacia: quello che va provato è il
comportamento.

### Il codice duplicato che ha diviso in due le pagine

Quando `dati()` ha imparato a classificare gli shot, il main di `artifact.py` è rimasto con la
sua copia del caricamento — senza classificazione. Risultato: la pagina di lavoro mostrava i
tre gruppi, quella autonoma e quella web no, e ogni buco cadeva nel default «scena». Due
sintomi diversi (tutti i buchi rossi, e la sezione in fondo vuota) da una sola causa: **la
stessa cosa fatta in due posti**.

### Tre difetti trovati provandola davvero

- **Graffe raddoppiate in una stringa che non era una f-string**: JavaScript invalido, e
  siccome lo script è uno solo la pagina moriva *tutta* — filtri compresi, che col player non
  c'entrano niente. Da fuori si vedeva solo «nessun bottone funziona». Ora `controlla_js` fa
  girare `node --check` **prima** di scrivere il file: se lo script è rotto, la pagina non
  viene nemmeno salvata.
- **Il riquadro di diagnosi accusava lo script quando cadeva un'immagine**, dicendo «i comandi
  sono fermi» mentre funzionavano. Ora distingue video, immagini ed errori veri, e tace se non
  ha niente da dire.
- **Dopo l'esportazione le modifiche restavano «in sospeso»**, così la pagina avvisava alla
  chiusura anche a lavoro salvato. Ora il conteggio distingue quelle esportate da quelle nuove.

### Il buio, come le immagini ferme

`MIN_MOTO` non basta: un fotogramma **quasi nero** accoppia con qualunque cosa e la grana si
muove eccome, quindi passava il voting. Misurato sui falsi emersi dalla riverifica: i due col
fotogramma vuoto stanno a 12,5 e 13,4 di deviazione standard, i veri confermati fra 48 e 71,
il primo percentile dei segmenti a 16,8. Da qui `MIN_CONTRASTO = 15`.

Il principio è lo stesso di `MIN_MOTO`, ed è il più generale del sottoprogetto: **un segmento
vale solo se il film, lì dentro, è verificabile.** Se non si muove o non si vede, la coerenza
temporale non sta dimostrando niente.

### Il recupero

Sugli shot rimasti scoperti le soglie si possono abbassare, perché non è più l'impronta a
decidere: ogni candidato passa da `controllo.py` e entra solo se supera il massimo dei
controlli casuali. Su 50 candidati ne sono entrati **48**, recuperando 36 shot e 12,3 minuti —
dal 70% al 76% del film.

### Cercare una cartella senza poterla elencare

Una pagina aperta col doppio clic non ha modo di guardare cosa c'è accanto a sé: può solo
chiedere un file preciso e vedere se risponde. Quindi «cerca una cartella qualsiasi» non
esiste — esiste un elenco corto di posti provati in ordine (`POSTI = ['', 'ANNA/', 'video/']`),
e vince il primo che risponde.

**Il segnale deve essere positivo — «questo file c'è» — mai l'assenza di un errore.** Un
`<video>` puntato su un file inesistente, servito via http, **non emette `error`**: emette
`stalled` e resta in attesa. Misurato: 15 s senza un evento utile, con un primo tentativo che
era un 404 arrivato in 5 ms. Un ripiego agganciato a `error` non scattava mai, e il sintomo era
«la pagina non trova i filmati» anche quando stavano nella seconda cartella dell'elenco.

I due ambienti rispondono in modi diversi e servono tutti e due: da server `fetch` dà 200 o 404
subito; da `file://` `fetch` è vietato e tira un'eccezione, e allora si prova a caricare davvero
aspettando `loadedmetadata`. `confronta` fa `await` sulla ricerca, se no un clic al primo secondo
punta al posto sbagliato.

## Cosa resta aperto

- I **confini** dei segmenti hanno la precisione del campionamento (±0,5 s) e la tolleranza
  del voting (±1 s). Vanno bene per una timeline, non per un montaggio.
- I 93 shot non ritrovati sono in coda a `relazione.md`. Non è detto che non ci siano nel
  girato: possono essere sotto la soglia, o a uno zoom fuori dalle cinque scale provate.
- Le tre famiglie incorporate nella pagina autonoma (Archivo, Newsreader, IBM Plex Mono)
  sono a licenza SIL OFL: si possono ridistribuire dentro il file. Le miniature sono
  fotogrammi del film e restano soggette ai diritti di chi li detiene.
- I cartelli (titoli, didascalie di restauro) danno match deboli e vanno letti con sospetto:
  sono testo bianco su nero, e si somigliano tutti.
