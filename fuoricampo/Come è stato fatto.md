# Come sono stati trovati i pezzi in comune

*Anna* di Grifi e Sarchielli dura tre ore e mezza ed è montato a partire da un girato molto
più lungo. Una parte di quel girato è arrivata fino a noi: Fuori Orario ha trasmesso il
*Fuori campo di Anna*, sei puntate per una quindicina di ore. Le due cose sono lo stesso
materiale a due stadi diversi della lavorazione, e la domanda è semplice da porre: preso un
pezzo qualsiasi del film, dove sta nel girato?

Trovarlo a mano vuol dire guardare quindici ore per ognuna delle trecento inquadrature del
film. Qui c'è come si è fatto a farlo fare al computer, cosa ha funzionato e — soprattutto —
cosa sembrava ovvio e invece era sbagliato.


## Perché non basta confrontare due immagini

Il primo istinto è: prendi un fotogramma del film, cerca il fotogramma più simile nel girato,
hai finito. Non funziona, e il motivo è nel materiale.

*Anna* è tutto in bianco e nero, girato quasi sempre nella stessa stanza, con le stesse
quattro o cinque persone, in piani lunghissimi. Un fotogramma del film assomiglia a mezz'ora
di girato. Non perché il metodo sia impreciso: perché sono davvero simili. Due primi piani
della stessa persona sullo stesso divano a dieci minuti di distanza sono, per un confronto
pixel a pixel, la stessa immagine.

Poi c'è che le due copie non si somigliano nemmeno quanto dovrebbero. Il girato è stato
ripreso in video da mezzo pollice; per farne un film, Grifi ha costruito una macchina che
rifilmava un monitor, un'inquadratura alla volta. Il risultato è che il montato è **ricadrato
più stretto** del girato, e di quanto cambia da ripresa a ripresa. Le prime coppie giuste che
sono uscite correlavano 0,80 dove due copie della stessa immagine dovrebbero stare a 0,98.

Quindi servono due cose: un modo di confrontare che regga il ricadramento, e qualcosa che
distingua un riuso vero da una somiglianza casuale.


## Il vicolo cieco dell'audio

Prima del video si è provato l'audio, e sembrava la strada giusta. L'audio non ha barre nere,
non ha il logo della rete, non ha il grading: è presa diretta di qua e presa diretta di là.

Ha dato 289 segmenti, **tutti falsi**. I motivi sono due e sono istruttivi.

Il primo: a trentadue bande mel, il parlato registrato in una stanza correla 0,87 con
qualunque altro parlato registrato nella stessa stanza. La mediana del *miglior* candidato era
0,87, cioè l'impronta non distingueva niente da niente. Il secondo: l'audio del film è
rimissato, quindi anche dove l'occhio conferma che il pezzo è quello, le due tracce non si
agganciano.

C'è poi un errore che è stato scoperto solo dopo, e che vale oltre l'audio. Per giudicare se
due spezzoni combaciavano si guardava la correlazione delle due forme d'onda su finestre da
trenta secondi. Il risultato era zero su venticinque, e sembrava la prova che non ci fossero
corrispondenze. Non lo era: era la prova che il giudice fosse rotto. Due copie passate per
catene diverse non hanno la stessa velocità al campione — basta uno scarto dello **0,02%**
perché su trenta secondi le due forme d'onda si sfasino di sei millisecondi, e la correlazione
crolli da 1,000 a 0,085, cioè al livello del rumore. Su finestre da due secondi lo stesso
scarto vale 0,4 millisecondi e la correlazione regge a 0,38.

Il video questo problema non ce l'ha, perché confronta fotogrammi singoli e non finestre.


## L'impronta

Ogni mezzo secondo, da entrambe le sorgenti, si tira fuori un fotogramma, lo si porta in scala
di grigi e lo si riduce a 24×24 pixel. Quei 576 numeri diventano un vettore a media zero e
norma uno, così il prodotto scalare fra due vettori *è* la loro correlazione. Il film fa 25 659
istanti, il girato 99 905: un unico prodotto di matrici sulla GPU li confronta tutti con tutti
in pochi secondi.

Ventiquattro per ventiquattro sembra pochissimo, ed è voluto. L'impronta non deve decidere:
deve **cercare**, cioè attraversare quindici ore in un paio di minuti e proporre dei
candidati. Il verdetto si dà dopo e altrove.

Due accorgimenti, entrambi nati da un errore.

**Le barre nere non sono uguali per tutti.** Ogni puntata è stata digitalizzata per conto suo
e l'immagine utile è larga 1151 pixel in quattro casi, 1057 in uno e 1044 in un altro. Con un
ritaglio unico l'impronta del girato inquadra una porzione diversa da quella del film e il
confronto crolla. Lo strumento standard per trovare le barre (`cropdetect`) qui sbaglia, perché
legge un fotogramma alla volta e prende per barra nera qualunque scena scura ai bordi: va
misurato il settantacinquesimo percentile della luminanza colonna per colonna, su qualche
centinaio di fotogrammi.

**La normalizzazione rende forte anche il vuoto.** Portare un vettore a norma uno vuol dire
che un fotogramma quasi senza contenuto — una parete grigia con un filo di luce in alto —
diventa un vettore lungo quanto un primo piano, e correla 0,93 con qualsiasi inquadratura
chiara sopra e scura sotto. Il novanta per cento dei primi falsi positivi era questo. Si toglie
proiettando via il gradiente lineare dall'immagine e buttando i fotogrammi che erano solo
gradiente.

Resta il ricadramento. Siccome lo zoom cambia da ripresa a ripresa — cercandolo su dieci
coppie confermate viene fra 0,70 e 0,96, senza un valore unico — l'unica strada è provare più
scale. Si estrae una volta sola a 48×48 e da lì si generano in memoria cinque riduzioni,
invece di ridecodificare quindici ore per ogni scala. Con questo il recall passa dal **6,5% al
70,5%** e la correlazione mediana delle coppie confermate da 0,50 a 0,83.


## Quello che distingue un riuso da una coincidenza

Qui sta il cuore. Un fotogramma simile non vuol dire niente, ne abbiamo già parlato. Quello che
vuol dire qualcosa è la **coerenza nel tempo**: per venti secondi di fila il girato avanza di
mezzo secondo ogni volta che il film avanza di mezzo secondo. La distanza fra i due orologi
resta costante. Quella non è una coincidenza, è la stessa ripresa.

Il conto si fa così: per ogni istante del film si tengono i cinque candidati migliori, poi si
parte dal primo che supera la soglia e si guarda fin dove la diagonale regge. Si tollera uno
scarto di un secondo sull'offset (le due copie derivano lentamente) e un buco di tre secondi
dentro la corsa. La prima corsa che arriva a tre secondi di lunghezza vince e si va avanti da lì.

Le soglie sono 0,70 sul singolo fotogramma per entrare nel voto e 0,80 di mediana perché il
segmento venga accettato. Sono basse di proposito: alzandole a 0,85/0,88 i minuti ritrovati
scendono da 198 a 50, e la precisione guardata a occhio è la stessa. Il numero di minuti da
solo non dice niente — sale sempre abbassando le soglie — e va letto insieme a un campione
guardato con gli occhi.


## Le due volte in cui il voto non dimostrava niente

Il metodo così com'è descritto ha sbagliato due volte, e le due volte si somigliano.

Un segnalatore aveva notato una cosa strana: il cartello «si consiglia la visione a un pubblico
adulto» risultava agganciato a una **targa incisa** ripresa nel girato. Guardando perché, viene
fuori un buco nel ragionamento. Su un'immagine ferma la coerenza temporale non dimostra
niente: una fila di sei fotogrammi identici «avanza in parallelo» a qualunque altra fila di sei
fotogrammi identici, quindi il voto — che è l'unica difesa contro le coincidenze — approvava
senza aver verificato nulla. E a 24×24 pixel un cartello e una targa sono lo stesso oggetto:
un rettangolo chiaro su fondo scuro.

Da lì la regola: un segmento vale solo se il film, lì dentro, **si muove**. Misurato: cartelli
e titoli di coda stanno fra 0,000 e 0,003, le inquadrature vere fra 0,018 e 0,318, e in mezzo
non c'è nessuno.

*Provata e buttata*: l'idea che i cartelli si riconoscessero dalla concentrazione dell'energia
nel vettore. Non separa niente — il cartello sta a 2,13 e la targa a 1,68, sotto la mediana del
film, in mezzo alle inquadrature vere.

La seconda volta è la stessa cosa al buio. Il movimento non basta, perché un fotogramma quasi
nero accoppia con qualsiasi cosa e la grana si muove eccome. I due falsi rimasti avevano il
fotogramma del film praticamente vuoto: deviazione standard 12,5 e 13,4, contro il 48÷71 dei
veri confermati. Da lì un minimo di contrasto, fissato a 15.

Il principio dietro entrambe, ed è il più generale di tutto il lavoro: **un segmento vale solo
se il film, lì dentro, è verificabile.** Se non si muove o non si vede, la coerenza temporale
non sta dimostrando un bel niente.


## Come si sa che è giusto

Per un po' la precisione è stata «nove su dieci a occhio, su un campione». Non è una misura.

Quello che la rende una misura è riprendere ogni segmento a piena risoluzione — 128×128 invece
di 24×24 — e cercare la geometria che allinea davvero le due immagini: zoom, spostamento e
istante esatto, dato che i confini valgono più o meno un secondo. Ne esce un punteggio
confrontabile fra segmenti. Costa due minuti per tutto il film.

Ma nemmeno un punteggio è una misura, se non si sa che punteggio prende una coppia sbagliata.
Quindi si prendono quaranta accoppiamenti a caso e si misurano allo stesso modo: mediana
**0,442**, massimo **0,648**. I segmenti veri stanno a mediana **0,827**, e **387 su 390 (99%)**
stanno sopra il massimo dei casuali.

È quel confronto a rendere il numero un'informazione. Un punteggio senza la sua distribuzione
nulla non dice se sei bravo o se il compito è facile.


## Dal 70% al 92%, in quattro passaggi

Il primo giro trova il 70% del film. Il resto è venuto fuori facendo quattro domande diverse.

**Gli shot che non hanno trovato niente.** Su quelli si possono abbassare le soglie, perché non
è più l'impronta a decidere: ogni candidato passa dalla verifica a piena risoluzione ed entra
solo se batte il massimo dei casuali. Cinquanta candidati, quarantotto confermati, dodici
minuti in più. Siamo al 76%.

**I pezzi che stanno dentro un segmento già trovato.** Una corsa si interrompe appena la
somiglianza scende per qualche campione, anche se nel girato la ripresa continua tranquillamente.
Lì non serve cercare — il segmento accanto dice già dove guardare — serve allungare finché la
verifica regge. Ventidue minuti in più, siamo all'86%.

Qui c'è una trappola che è costata un giro a vuoto: **la soglia per riconoscere non è quella per
prolungare**. Appena fuori dal bordo di un segmento la verifica dà comunque 0,674, perché dentro
una ripresa continua i fotogrammi vicini si somigliano tutti. Con la soglia dei casuali
(0,648) l'estensione non si ferma mai e la copertura gonfia oltre la durata del film.

**I buchi dentro gli shot agganciati a metà.** Allungare tiene fermo l'offset del segmento
vicino, e lì si ferma. Ma cercandoli senza quel vincolo, **trentacinque dei quarantanove
confermati stanno in un punto diverso del girato** — spesso qualche decina di secondi più in
là. Non è un difetto del metodo: è il montaggio. Dentro quella che il rilevatore vede come una
sola inquadratura, Grifi ha ricucito materiale preso da momenti diversi del ciak. Cercare
invece di allungare vale dodici minuti e mezzo, e siamo al 92%.

**Le scene lunghe e ferme.** Su un primo piano di cinque minuti che si muove poco, ogni
fotogramma somiglia a decine di punti del girato, il candidato migliore salta di qua e di là e
la diagonale non si forma. Si può votare in un altro modo: prendere tutti i candidati dello
shot e tenere l'offset più votato, perché non conta che i match siano ordinati, conta che siano
d'accordo. Resa: poca. Sette proposte, cinque vere guardandole — 71% di precisione contro il
98% del resto — per meno di un minuto. Sono entrate solo le cinque verificate a occhio.

Ed è anche il punto in cui conviene fermarsi: applicare tutto avrebbe peggiorato la qualità del
risultato per un guadagno trascurabile.


## Due modi di contare che sembrano uguali e non lo sono

Dopo l'estensione i segmenti vicini si allungano l'uno verso l'altro e si sovrappongono.
Sommando le loro durate venivano 322 minuti su un film che ne dura 214. Il numero impossibile
ha salvato la misura: la somma delle durate dice quanto materiale è stato accoppiato, la
copertura è l'**unione** degli intervalli, e sono due cose diverse. La stessa svista era già
comparsa altrove nel progetto, e va cercata ogni volta che si mettono insieme due insiemi che
possono intersecarsi.

E un'estrapolazione fatta su un campione sparso sovrastima sempre, perché in un campione le
sovrapposizioni non ci sono.


## Cosa entra nel confronto e cosa no

Le puntate trasmesse sono sei, ma nel confronto ne entrano cinque.

La sesta non è girato: è un rimontaggio delle altre. Misurato con lo stesso metodo e le stesse
soglie, usando la sesta come se fosse il film, **74 dei suoi 95 minuti (78%) si ritrovano nelle
altre puntate**. Tenendola dentro, il montato si agganciava alla copia invece che
all'originale, e siccome la ricerca è greedy quei pezzi non venivano nemmeno più cercati
altrove. Toltala, quindici segmenti sono tornati alla puntata da cui vengono e il totale non si
è mosso di mezzo punto — che è il modo in cui questo genere di errore si nasconde: non peggiora
i numeri, sposta le attribuzioni.

La prima invece resta, e sta allo zero per cento. Non è un difetto: non è girato nemmeno
quella, è la presentazione al festival — il dibattito con Grifi e Sarchielli dopo la
proiezione, tavolo, microfoni, pubblico, con i cartelli sul restauro in apertura. Nel parlato
si sente da dove viene: «la copia è stata pagata dalla Biennale di Venezia». Non contiene un
fotogramma del film perché non può contenerlo, e lo zero è la risposta giusta.


## Dove si è arrivati

**390 segmenti, 198 minuti di film ritrovati su 214 (92%), 214 shot su 307.** La verifica a
piena risoluzione conferma 387 su 390.

I sedici minuti che restano scoperti si dividono in due metà diverse fra loro. Sette e mezzo
sono cartelli, didascalie e fotogrammi neri: roba fatta in montaggio, che nel girato non può
esistere per definizione. Gli altri otto e mezzo sono scene vere, e quelle o stanno in una
puntata mai trasmessa o ci sono sfuggite.

C'è poi il rovescio, che è la parte grossa e che di solito nessuno guarda: delle dodici ore e
mezza di girato, **nove non compaiono nel film**. Il blocco più lungo è un'ora e mezza di
seguito. Sta in una pagina a parte, `Il girato scartato.html`.


## Se ti serve rimetterci le mani

Il metodo in dettaglio, con tutti i numeri e le cose provate e buttate, sta in `README.md`.
Quello che resta da fare, in `PIANO.md`. Gli script si lanciano in quest'ordine:

```
impronta.py      da ogni video a un vettore ogni mezzo secondo
match.py --video le diagonali, cioè i segmenti           -> segmenti-video.json
controllo.py     la verifica a 128×128                   -> controllo.json
recupero.py      gli shot rimasti a mani vuote
estendi.py       allunga fin dove la verifica regge
buchi.py         cerca dentro gli shot coperti a metà
artifact.py      la pagina da guardare e da mandare in giro
scartato.py      il rovescio: il girato mai usato
```

Una cosa da tenere presente rilanciandoli: non si confrontano numeri fra run con parametri
diversi. Ogni cifra va citata con la condizione in cui è stata presa, o si finisce a discutere
di due cose diverse credendo che siano la stessa.
