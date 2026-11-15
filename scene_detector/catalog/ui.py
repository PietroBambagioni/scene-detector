from __future__ import annotations

import base64
import html
import json
import re
from functools import lru_cache
from pathlib import Path

FONT = Path(__file__).parent / "font"


@lru_cache(maxsize=1)
def _font_face() -> str:
    """Gli `@font-face` coi woff2 dentro, come data URI. -> CSS, o "" se i font non ci sono.

    Una pagina che si apre col doppio click non puo' linkare Google Fonts: il `<link>` fallisce
    in silenzio e si cade sui font di sistema. I file sono il solo sottoinsieme `latin` (268 KB
    contro 1 MB) e sono SIL OFL, quindi ridistribuibili dentro l'HTML. Il `google.css` accanto
    porta i metadati (famiglia, peso, `unicode-range`): riscriverli a mano e' come sbagliano.
    """
    css = FONT / "google.css"
    if not css.exists():
        return ""                       # pacchetto senza i font: si cade sui fallback di sistema
    fuori = []
    for commento, blocco in re.findall(r"/\* (\w[\w-]*) \*/\s*(@font-face \{.*?\})",
                                       css.read_text(), re.S):
        if commento != "latin":
            continue
        nome = re.search(r"url\((https://[^)]+\.woff2)\)", blocco).group(1).rsplit("/", 1)[1]
        f = FONT / nome
        if not f.exists():
            continue
        dato = "data:font/woff2;base64," + base64.b64encode(f.read_bytes()).decode()
        fuori.append(re.sub(r"url\(https://[^)]+\.woff2\)", f"url({dato})", blocco))
    return "\n".join(fuori)

_TEMPLATE = """<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — Catalogo scene</title>
<style>
__FONT__
/* Stessa lingua della pagina del *Fuori campo* (`prove/fuoricampo/artifact.py`): niente angoli
   arrotondati, filetti da un pixel, etichette in monospaziato maiuscolo, e lo stato acceso e'
   l'**inversione** inchiostro/fondo invece di un colore d'accento. Chiaro di default, scuro
   quando lo chiede il sistema: la pagina non ha un interruttore, quindi non c'e' `[data-theme]`
   da rincorrere. */
:root {
  color-scheme: light dark;
  --fondo:#F4F5F3; --carta:#FFFFFF; --inchiostro:#14161A; --tenue:#5C6169;
  --linea:#DEE0DC; --linea-forte:#C9CCC7; --pista:#E7E9E5;
  /* Due famiglie con un significato, come di la': il **freddo** e' cio' che si sa (minutaggi,
     selezione), il **caldo** e' cio' che chiede attenzione (non esportato, confini incerti).
     Sul chiaro sono piu' scuri delle tinte del *Fuori campo*: li' fanno da fondo a testo bianco,
     qui sono **testo** su fondo chiaro, e a 3,58 e 4,20 stavano sotto il 4,5 che serve. Misurato
     sul tema che non stavo guardando — sullo scuro erano gia' a 7,8 e 9,4. */
  --freddo:#287A8A; --caldo:#B05800;
  --display:"Archivo","Helvetica Neue",Arial,sans-serif;
  --corpo:"Newsreader",Georgia,"Times New Roman",serif;
  --mono:"IBM Plex Mono",ui-monospace,"SF Mono",Menlo,monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --fondo:#0E1013; --carta:#171A1E; --inchiostro:#E8E9E6; --tenue:#959BA4;
    --linea:#252930; --linea-forte:#39404A; --pista:#1D2126;
    --freddo:#4FB3C6; --caldo:#FFA03D;
  }
}
* { box-sizing:border-box; }
/* `main { display:grid }` e' una regola d'autore e batte il `[hidden]` del browser, che e' una
   regola d'agente: senza questa riga «nascondi» non nasconde e le due viste si sovrappongono. */
[hidden] { display:none !important; }
html { background:var(--fondo); }
/* Colonna flex alta quanto la finestra: testata, timeline, cast e filtri stanno fermi, e l'unica
   cosa che scorre e' il contenuto. Prima l'altezza era `calc(100vh - 84px)`, cioe' la somma a
   mano di testata e timeline — e bastava che comparisse la striscia del cast per sballare. */
body { margin:0; background:var(--fondo); color:var(--inchiostro);
       font:14px/1.5 var(--display); -webkit-font-smoothing:antialiased;
       height:100vh; display:flex; flex-direction:column; overflow:hidden; }
header, #timeline, #cast, #filtri { flex:0 0 auto; }
main, #pannello { flex:1 1 auto; min-height:0; }
:focus-visible { outline:2px solid var(--inchiostro); outline-offset:1px; }

/* --- comandi: squadrati, monospaziati, acceso = invertito ------------------ */
input, button, textarea, select { font-family:var(--mono); font-size:.78rem; border-radius:0; }
button { padding:.32rem .62rem; border:1px solid var(--linea-forte); background:transparent;
         color:var(--inchiostro); cursor:pointer; white-space:nowrap; }
button:hover:not(:disabled) { border-color:var(--inchiostro); }
button:disabled { opacity:.35; cursor:default; }
button[aria-pressed="true"] { background:var(--inchiostro); color:var(--fondo);
                              border-color:var(--inchiostro); }
#filter, #filterDescr, #speed { padding:.32rem .55rem; border:1px solid var(--linea-forte);
                  background:var(--carta); color:var(--inchiostro); }
#filter::placeholder, #filterDescr::placeholder { color:var(--tenue); }
#filter { min-width:11rem; }
#filterDescr { min-width:10rem; }

/* menu d'esportazione: `<details>` fa apertura e chiusura da solo, e con la tastiera funziona
   senza scrivere niente */
.menu { position:relative; }
.menu summary { list-style:none; cursor:pointer; padding:.32rem .62rem;
                border:1px solid var(--linea-forte); font-family:var(--mono); font-size:.78rem; }
.menu summary::-webkit-details-marker { display:none; }
.menu summary:hover, .menu[open] summary { border-color:var(--inchiostro); }
.menu .voci { position:absolute; right:0; top:calc(100% + 3px); z-index:5; display:flex;
              flex-direction:column; min-width:15rem; background:var(--fondo);
              border:1px solid var(--inchiostro); }
.menu .voci button { border:0; border-bottom:1px solid var(--linea); text-align:left;
                     padding:.45rem .6rem; }
.menu .voci button:last-child { border-bottom:0; }
.menu .voci button:hover { background:var(--carta); }
.menu .voci b { font-family:var(--mono); }
.menu .voci small { display:block; font-family:var(--corpo); font-size:12px; color:var(--tenue); }
textarea { width:100%; min-height:70px; padding:.55rem .65rem; border:1px solid var(--linea);
           background:var(--carta); color:var(--inchiostro); resize:vertical;
           font-family:var(--corpo); font-size:15px; line-height:1.55; }
textarea:focus { outline:none; border-color:var(--inchiostro); }
label, .lab { font-family:var(--mono); font-size:.64rem; letter-spacing:.14em;
              text-transform:uppercase; color:var(--tenue); }

/* --- testata --------------------------------------------------------------- */
/* `z-index:3` e non 2: la testata e' un contesto d'impilamento e il menu d'esportazione ci vive
   dentro, quindi si confronta con la timeline **come testata**, non come menu. A pari z-index
   vinceva la timeline, che viene dopo nel documento, e la prima voce spariva sotto. */
header { display:flex; gap:12px; align-items:center; padding:.6rem 1rem;
         border-bottom:1px solid var(--inchiostro); background:var(--fondo);
         position:relative; z-index:3; flex-wrap:wrap; }
header h1 { font-family:var(--display); font-weight:800; font-size:1rem; margin:0;
            letter-spacing:-.01em; white-space:nowrap; }
header .meta { font-family:var(--mono); font-size:.68rem; letter-spacing:.06em;
               color:var(--tenue); white-space:nowrap; }
header .spacer { flex:1; }
#saved { font-family:var(--mono); font-size:.7rem; color:var(--caldo); margin-left:auto;
         display:flex; gap:.4rem; align-items:center; }

/* --- timeline -------------------------------------------------------------- */
#timeline { display:flex; align-items:center; height:38px; padding:0 1rem;
            border-bottom:1px solid var(--linea); background:var(--fondo); }
#track { position:relative; flex:1; height:20px; background:var(--pista);
         border:1px solid var(--linea); }
#bands { position:absolute; inset:0; overflow:hidden; }
.band { position:absolute; top:0; height:100%; cursor:pointer; }
.band.alt { background:color-mix(in srgb, var(--inchiostro) 7%, transparent); }
.band.cur { background:color-mix(in srgb, var(--freddo) 26%, transparent); }
.pin { position:absolute; top:0; height:100%; width:1px; background:var(--linea-forte);
       cursor:pointer; }
.pin:hover { background:var(--inchiostro); width:2px; }
.pin.active { background:var(--freddo); width:3px; margin-left:-1px; z-index:1; }

/* --- corpo ----------------------------------------------------------------- */
/* `minmax(0,1fr)` e non `1fr`: `1fr` vale `minmax(auto,1fr)`, e quel minimo e' il **contenuto
   minimo** della colonna — una riga di scena con miniatura e bottoni non scende sotto i 519px e
   la pagina sfora di lato invece di stringersi. */
main { display:grid; grid-template-columns:minmax(15rem,22rem) minmax(0,1fr); }
#list { overflow:auto; border-right:1px solid var(--linea); }
#detail { padding:1rem; overflow:auto; display:flex; flex-direction:column; gap:.7rem; }
/* La colonna scorre, quindi **niente** qui dentro deve stringersi per far stare il resto: un
   bottone senza altezza minima si schiaccia a una fetta di pixel e il suo testo sparisce. */
#detail > * { flex-shrink:0; }
video { width:100%; max-height:52vh; background:#000; }
.nav { display:flex; gap:.4rem; align-items:center; flex-wrap:wrap; }
.tc { font-family:var(--mono); font-size:.78rem; color:var(--freddo);
      font-variant-numeric:tabular-nums; }

/* --- righe della lista ----------------------------------------------------- */
.item { display:flex; gap:9px; padding:.5rem .9rem; border-bottom:1px solid var(--linea);
        cursor:pointer; }
.item img { width:58px; height:33px; object-fit:cover; background:var(--pista); flex:0 0 auto; }
.item .c { flex:1; min-width:0; }
.item:hover { background:var(--carta); }
.item.sel { background:color-mix(in srgb, var(--freddo) 16%, transparent);
            box-shadow:inset 3px 0 0 var(--freddo); }
.item .h { display:flex; justify-content:space-between; gap:.5rem; font-family:var(--mono);
           font-size:.68rem; color:var(--freddo); font-variant-numeric:tabular-nums;
           white-space:nowrap; }
/* Il minutaggio andava a capo quando accanto compariva il perche', e righe di altezza diversa
   fanno ballare la fila mentre la scorri. */
.item .h span { flex:0 0 auto; }
.item .d { font-family:var(--corpo); color:var(--tenue); font-size:13px; margin-top:2px;
           max-height:3em; overflow:hidden; }
.perche { color:var(--caldo); font-variant-numeric:tabular-nums; }
#coda { padding:.55rem .9rem; border-bottom:1px solid var(--inchiostro);
        font-family:var(--mono); font-size:.68rem; color:var(--tenue);
        display:flex; gap:.6rem; align-items:center; }
#coda b { color:var(--caldo); font-weight:500; }

/* --- scene ----------------------------------------------------------------- */
.scene { border-bottom:1px solid var(--linea); }
.sh { display:flex; gap:9px; align-items:flex-start; padding:.5rem .6rem; cursor:pointer; }
.sh:hover { background:var(--carta); }
.scene.cur > .sh { background:color-mix(in srgb, var(--freddo) 10%, transparent); }
.sh .chev { color:var(--tenue); flex:0 0 14px; font-size:12px; line-height:1.4;
            text-align:center; padding:2px 0; }
.sh .chev:hover { color:var(--inchiostro); }
.sh img { width:92px; height:52px; object-fit:cover; background:var(--pista); flex:0 0 auto; }
.sh .b { flex:1; min-width:0; }
.sh .t { display:flex; justify-content:space-between; gap:8px; font-family:var(--mono);
         font-size:.68rem; color:var(--freddo); font-variant-numeric:tabular-nums; }
.sh .t .nome { color:var(--inchiostro); font-family:var(--display); font-weight:600;
               font-size:.8rem; }
.sh .who { font-family:var(--mono); font-size:.64rem; letter-spacing:.04em; color:var(--tenue);
           overflow:hidden; text-overflow:ellipsis; white-space:nowrap; margin-top:2px; }
/* I comandi della scena escono solo dove stai lavorando: sette bottoni per riga, su trentacinque
   scene, sono un muro che copre la cosa da leggere (il nome, i minuti, chi c'e' dentro). */
.acts { display:none; gap:.25rem; margin-top:.4rem; flex-wrap:wrap; align-items:center; }
.scene.cur > .sh .acts, .sh:hover .acts { display:flex; }
.acts button { padding:.1rem .4rem; font-size:.66rem; }
/* etichetta e frecce sono una cosa sola: mandando a capo fra ◀ e ▶ non si capisce piu' a che
   confine appartengono */
.gruppo { display:inline-flex; gap:.25rem; align-items:center; white-space:nowrap; }
.gruppo .lab { margin-right:.1rem; }
input.rinomina { font-family:var(--display); font-size:.8rem; padding:1px .3rem;
                 border:1px solid var(--inchiostro); background:var(--carta);
                 color:var(--inchiostro); width:14em; }
.shots { display:none; }
.scene.open .shots { display:block; }
.scene .item { padding-left:1.5rem; }

/* --- dialogo a comparsa, nel pannello dello shot --------------------------- */
/* L'anteprima del testo puo' essere lunga quanto vuole, e i bottoni sono `nowrap`: senza il
   taglio, la riga «▸ Descrizione · L'immagine mostra…» diventa larga 495px e su un telefono e'
   lei a far scorrere la pagina di lato. */
.dlgtoggle { display:block; width:100%; text-align:left; overflow:hidden;
             text-overflow:ellipsis; }
.dlg { font-family:var(--corpo); font-size:15px; line-height:1.55; color:var(--inchiostro);
       white-space:pre-wrap; border-left:2px solid var(--linea-forte); padding-left:.7rem; }

/* --- cast ------------------------------------------------------------------ */
#cast { display:flex; gap:.6rem; overflow-x:auto; padding:.5rem .9rem;
        border-bottom:1px solid var(--linea); }
#cast:empty { display:none; }
#filtri { display:flex; gap:.3rem; align-items:center; padding:.4rem .9rem; flex-wrap:wrap;
          border-bottom:1px solid var(--linea); }
#filtri.spento { display:none; }
#filtri button { font-size:.66rem; padding:.16rem .5rem; }
#filtri .lab { margin-right:.2rem; }
#quanti { font-family:var(--mono); font-size:.66rem; color:var(--tenue); margin-left:auto; }

/* --- scheda del film ------------------------------------------------------- */
#pannello { padding:1.2rem 1.2rem 3rem; max-width:78rem; overflow:auto; }
#pannello h2 { font-family:var(--mono); font-size:.66rem; letter-spacing:.14em;
               text-transform:uppercase; color:var(--tenue); font-weight:400;
               margin:2rem 0 .7rem; }
#pannello h2:first-of-type { margin-top:.4rem; }
/* i filetti sono il `gap`, come nella pagina del *Fuori campo*: una griglia sopra una linea */
.cifre { display:grid; grid-template-columns:repeat(auto-fit,minmax(9rem,1fr)); gap:1px;
         background:var(--linea); border:1px solid var(--linea); }
.cifra { background:var(--fondo); padding:.9rem 1rem; }
.cifra b { display:block; font-family:var(--mono); font-weight:500; font-size:1.5rem;
           letter-spacing:-.02em; }
.cifra span { font-family:var(--mono); font-size:.62rem; letter-spacing:.1em;
              text-transform:uppercase; color:var(--tenue); }
/* barre: una sola serie, quindi un solo colore e nessuna legenda — il titolo la nomina */
.barre { display:flex; flex-direction:column; gap:2px; max-width:44rem; }
.barra { display:grid; grid-template-columns:7.5rem 1fr auto; gap:.6rem; align-items:center;
         font-family:var(--mono); font-size:.7rem; }
.barra .n { color:var(--tenue); text-align:right; font-variant-numeric:tabular-nums; }
.barra .p { height:14px; background:var(--pista); }
.barra .p i { display:block; height:100%; background:var(--freddo); }
.barra .e { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--tenue); }
#ritmo { position:relative; height:120px; background:var(--pista); border:1px solid var(--linea);
         margin-bottom:.4rem; }
#ritmo i { position:absolute; bottom:0; background:var(--freddo); min-width:1px; cursor:pointer; }
#ritmo i:hover { background:var(--inchiostro); }
.assex { display:flex; justify-content:space-between; font-family:var(--mono);
         font-size:.62rem; color:var(--tenue); }

/* --- aiuto ----------------------------------------------------------------- */
/* Una colonna sola larga 62 caratteri lasciava vuoti due terzi dello schermo. Le sezioni vanno
   in griglia — la stessa dei riquadri della scheda, con i filetti fatti dal `gap` — e ognuna si
   tiene la sua misura di lettura. Le due che sono tabelle prendono tutta la larghezza. */
.aiuto { display:grid; grid-template-columns:repeat(auto-fit,minmax(21rem,1fr)); gap:1px;
         background:var(--linea); border:1px solid var(--linea); align-items:start; }
.aiuto section { background:var(--fondo); padding:1rem 1.2rem; height:100%; }
.aiuto section.largo { grid-column:1 / -1; }
.aiuto h2 { margin:0 0 .7rem; }
.aiuto p, .aiuto li { font-family:var(--corpo); font-size:15px; line-height:1.6;
                      max-width:62ch; color:var(--inchiostro); }
.aiuto p { margin:0 0 .6rem; }
.aiuto ul { margin:0 0 .6rem; padding-left:1.1rem; }
.aiuto li { margin-bottom:.35rem; }
.aiuto b { font-family:var(--display); font-weight:600; }
.aiuto .nota { color:var(--tenue); }
kbd { font-family:var(--mono); font-size:.72rem; padding:.1rem .4rem; border:1px solid var(--linea-forte);
      color:var(--inchiostro); white-space:nowrap; }
.tasti { display:grid; grid-template-columns:repeat(auto-fit,minmax(19rem,1fr)); gap:1px;
         background:var(--linea); border:1px solid var(--linea); }
.tasti div { background:var(--fondo); padding:.5rem .8rem; display:flex; gap:.7rem;
             align-items:baseline; font-family:var(--corpo); font-size:14px; }
.tasti div span:first-child { flex:0 0 6.5rem; }
.castcard { flex:0 0 auto; display:flex; flex-direction:column; align-items:center; gap:3px;
            width:88px; cursor:pointer; padding:4px; border:1px solid transparent; }
.castcard:hover { background:var(--carta); }
.castcard.active { border-color:var(--inchiostro); background:var(--carta); }
/* fusione in corso: il primo scelto e' pieno, gli altri sono i bersagli possibili */
.castcard.dafondere { background:var(--inchiostro); }
.castcard.dafondere input, .castcard.dafondere .n { color:var(--fondo); }
.castcard.bersaglio { border-color:var(--caldo); border-style:dashed; }
.castcard .fondi { position:absolute; top:2px; right:2px; padding:0 .25rem; font-size:.6rem;
                   opacity:0; }
.castcard { position:relative; }
.castcard:hover .fondi, .castcard.dafondere .fondi { opacity:1; }
#fondiAvviso { font-family:var(--mono); font-size:.66rem; color:var(--caldo);
               padding:.3rem .9rem; border-bottom:1px solid var(--linea); }
#fondiAvviso[hidden] { display:none; }
.castcard img, .castcard .ph { width:52px; height:52px; object-fit:cover; background:var(--pista);
       display:flex; align-items:center; justify-content:center; color:var(--tenue);
       font-size:18px; }
.castcard input { width:100%; text-align:center; font-family:var(--display); font-size:.72rem;
                  padding:1px 2px; border:1px solid transparent; background:transparent;
                  color:var(--inchiostro); }
.castcard input:hover, .castcard input:focus { border-color:var(--linea-forte);
                                               background:var(--carta); outline:none; }
.castcard .n { font-family:var(--mono); font-size:.6rem; letter-spacing:.06em;
               color:var(--tenue); }
/* volto che il rilevatore non riconosce come umano: mostrato, ma dichiarato inaffidabile */
.castcard.unc img, .castcard.unc .ph { opacity:.45; }
.castcard.unc .n { color:var(--caldo); }

/* --- schermi stretti ------------------------------------------------------- */
/* Sotto i 900px le due colonne non ci stanno: la lista va sopra e il dettaglio sotto, e la
   pagina torna a scorrere per intero invece di tenere tutto dentro l'altezza della finestra —
   su un telefono un pannello alto 30vh dentro una pagina ferma e' inusabile. */
@media (max-width:900px) {
  body { height:auto; overflow:auto; }
  main { grid-template-columns:minmax(0,1fr); }
  #list { max-height:45vh; border-right:0; border-bottom:1px solid var(--linea); }
  #detail { overflow:visible; }
  header { position:sticky; top:0; }
  header .spacer { display:none; }
  header h1 { font-size:.9rem; }
  #filter, #filterDescr { flex:1 1 9rem; min-width:0; }
  video { max-height:38vh; }
  .barra { grid-template-columns:5.5rem 1fr auto; }
}
@media (max-width:560px) {
  header .meta { display:none; }        /* i conteggi stanno anche nella scheda */
  #detail, #pannello { padding:.8rem; }
  .item img { width:44px; height:25px; }
  .sh img { width:64px; height:36px; }
  /* il `nowrap` dei minutaggi e' quello che tiene le righe alte uguali mentre scorri: qui pero'
     diventa una larghezza minima che non si puo' rispettare, e allora si lascia andare a capo */
  .item .h, .sh .t { flex-wrap:wrap; white-space:normal; }
  .item .h span, .sh .t span { flex:0 1 auto; }
}

/* --- chip dei personaggi sullo shot ---------------------------------------- */
#chips { display:flex; flex-wrap:wrap; gap:.3rem; }
.chip { font-family:var(--mono); font-size:.68rem; padding:.16rem .5rem;
        border:1px solid var(--linea-forte); color:var(--inchiostro); cursor:pointer; }
.chip:hover { border-color:var(--inchiostro); }
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <div class="meta" id="meta"></div>
  <div class="spacer"></div>
  <input id="filter" placeholder="cerca nei dialoghi…">
  <input id="filterDescr" placeholder="…nelle descrizioni">
  <button id="aiuto" aria-pressed="false" title="come si usa questa pagina, e tutte le scorciatoie (H)">? aiuto</button>
  <button id="scheda" aria-pressed="false" title="i numeri del film: ritmo, durate, personaggi (T)">⊞ scheda</button>
  <button id="rivedi" aria-pressed="false" title="rivedi i confini incerti, dal piu' incerto (R)">⚑ rivedi</button>
  <button id="annulla" title="annulla l'ultima modifica di struttura (⌘Z)">↶ annulla</button>
  <details class="menu" id="menuExport">
    <summary>↓ esporta</summary>
    <div class="voci">
      <button id="export"><b>JSON</b><small>il catalogo corretto — il file da rimandare indietro</small></button>
      <button id="edl"><b>EDL</b><small>lista di montaggio CMX3600, per Premiere o Resolve</small></button>
      <button id="srt"><b>SRT</b><small>sottotitoli dai dialoghi trascritti</small></button>
    </div>
  </details>
</header>
<div id="timeline"><div id="track"><div id="bands"></div></div></div>
<div id="cast"></div>
<div id="fondiAvviso" hidden></div>
<div id="filtri"></div>
<main id="main">
  <div id="list"></div>
  <div id="detail">
    <video id="player" controls preload="metadata"></video>
    <div class="tc" id="tc"></div>
    <div class="nav">
      <button id="back5" title="5 secondi indietro (attraversa i confini dello shot)">⏪ 5s</button>
      <button id="fwd5" title="5 secondi avanti (attraversa i confini dello shot)">5s ⏩</button>
      <select id="speed" title="velocità di riproduzione">
        <option value="0.25">0,25×</option>
        <option value="0.5">0,5×</option>
        <option value="1" selected>1×</option>
        <option value="2">2×</option>
      </select>
      <button id="stopend" aria-pressed="false" title="si ferma sull'ultimo frame dello shot invece di proseguire">⏹ stop a fine shot</button>
    </div>
    <div class="nav">
      <button id="fprev" title="un fotogramma indietro (←)">◀ 1f</button>
      <span class="tc" id="frame"></span>
      <button id="fnext" title="un fotogramma avanti (→)">1f ▶</button>
      <button id="split" title="spezza questo shot al fotogramma sul player (S)">✂ taglia qui</button>
      <button id="mergeprev" title="fondi questo shot nel precedente (M)">⤴ unisci al prec</button>
    </div>
    <div id="chips"></div>
    <button id="dlgLabel" class="dlgtoggle" aria-expanded="false"
            title="mostra il dialogo di questo shot (D)">▸ Dialogo</button>
    <textarea id="dialogue" hidden></textarea>
    <button id="descrLabel" class="dlgtoggle" aria-expanded="false"
            title="mostra la descrizione di questo shot (E)">▸ Descrizione</button>
    <textarea id="description" hidden placeholder="(descrizione visiva — da generare)"></textarea>
    <div class="nav">
      <button id="prev">◀ Prec</button>
      <button id="next">Succ ▶</button>
      <span id="saved"></span>
    </div>
  </div>
</main>
<div id="pannello" hidden></div>
<script>
const DATA = __DATA__;
const shots = DATA.shots;
const cast = DATA.cast || [];
const castById = {};
cast.forEach(c => castById[c.id] = c);
// Senza `--scenes` il manifest non ha la chiave: `scenes` resta null e ogni ramo qui sotto
// ricade sul comportamento a due livelli. E' opt-in, quindi e' il caso piu' comune.
const scenes = DATA.scenes || null;
const open = new Set();          // scene espanse: si apre quella corrente, le altre restano chiuse
// Quale scena ha aperto `select` l'ultima volta. Senza, `select` riapriva la scena corrente a
// **ogni** chiamata: chiudevi col chevron e la prima freccia la rispalancava, cioe' il bottone
// sembrava rotto. Aprire ha senso quando si **cambia** scena, non mentre ci si muove dentro.
let scenaAperta = -1;
// Dialoghi aperti, per `start_frame` e non per indice: un taglio manuale sposta di uno tutti gli
// indici a valle, e il pannello aperto passerebbe allo shot sbagliato. Parte vuoto: tutti chiusi.
// Dialogo e descrizione stanno nel pannello dello shot, non nelle righe della lista: e' li' che
// li leggi e li correggi. Sono i due testi lunghi, e con tutt'e due aperti il player finisce
// fuori schermo. Uno stato per ciascuno, chiusi all'avvio, che **restano** cambiando shot —
// aprirli a ogni riga per rileggere una battuta dopo l'altra sarebbe un clic di troppo per volta.
let dlgAperto = false, descrAperto = false;
let forzaDlg = false;            // nella lista il testo compare solo mentre cerchi: nascondere
                                 // la riga che hai appena trovato non ha senso
let playing = null;              // riproduzione di una scena su clip separate: {sc, i}
let charFilter = null;
let cur = -1;
const $ = id => document.getElementById(id);
const fmt = t => { t = Math.max(0, t|0); const m=(t/60)|0, s=t%60; return m+':'+String(s).padStart(2,'0'); };
// anche `"`: `esc` finisce dentro `value="…"` e `title="…"`, e un nome come «Mario "il rosso"»
// chiudeva l'attributo — alla riapertura il personaggio si chiamava «Mario »
const esc = s => s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

// funzione e non riga secca: unisci/dividi cambiano il conteggio delle scene
function renderMeta() {
  $('meta').textContent = `${DATA.video} · ${DATA.n_shots} shot`
    + (scenes ? ` · ${scenes.length} scene` : '') + ` · ${DATA.detector}`;
}

// Con --split-mode none non ci sono clip: si riproduce il film originale spostando currentTime,
// non riassegnando src a ogni click. Il media fragment #t= era inaffidabile — cambiare solo il
// frammento non fa ricaricare, e ricaricare 2,7 GB a ogni click e' comunque lento. Qui il film
// si carica UNA volta, poi ogni shot e' un seek + play che si ferma a fine shot.
const FILM = DATA.video_src || null;
// `stopAt` e' il tempo dove la riproduzione *che abbiamo avviato noi* deve fermarsi, `Infinity`
// quando non deve fermarsi affatto. Di default si prosegue oltre il confine dello shot: e' il
// toggle qui sotto ad armarlo, e `playScene` che lo arma sempre (suonare una scena e' un'altra
// cosa: si ferma dove finisce la scena, toggle o no).
let stopShot = false;
let stopAt = Infinity;
if (FILM) {
  $('player').src = FILM;
  $('player').addEventListener('timeupdate', () => {
    const p = $('player');
    if (p.currentTime < stopAt) return;
    const fine = stopAt;
    // Disarmare **prima** di riposizionare: il `timeupdate` arriva fino a 250 ms dopo il confine,
    // quindi si torna indietro sull'ultimo frame — e con `stopAt` ancora armato il play seguente
    // ripauserebbe dopo mezzo frame, cioe' il video sembrerebbe bloccato.
    stopAt = Infinity;
    p.pause();
    p.currentTime = fine - 0.5 / DATA.fps;     // mezzo frame dentro: e' l'ultimo frame dello shot
  });
  // `stopAt` vincola *la riproduzione che abbiamo avviato noi*, non il player: appena l'utente
  // interviene va disarmato, altrimenti il timeupdate rimette in pausa e il film sembra rotto.
  // Due interventi, due casi, ed e' il secondo quello che si nota:
  //  - seek sulla barra oltre lo shot corrente -> ripartirebbe in pausa
  //  - play a fine shot (siamo fermi *su* stopAt) -> non riparte affatto, nessun seek di mezzo
  // Niente flag da tenere in sincrono: basta guardare dove si trova la testina.
  $('player').addEventListener('seeked', () => {
    const sh = shots[cur], t = $('player').currentTime;
    if (!sh || t < sh.start_time || t > sh.end_time) stopAt = Infinity;
  });
  $('player').addEventListener('play', () => {
    if ($('player').currentTime >= stopAt) stopAt = Infinity;
  });
}

function seekTo(sh, ferma = stopShot) {
  const p = $('player');
  stopAt = ferma ? sh.end_time : Infinity;
  const go = () => { p.currentTime = sh.start_time; p.play().catch(() => {}); };
  if (p.readyState >= 1) go();                 // metadati pronti: seek subito
  else p.addEventListener('loadedmetadata', go, { once: true });
}

// ----------------------------------------------------------------- scene ---
// Le scene sono una vista *sopra* gli shot: `cur` resta un indice di shot, non cambia sistema
// di coordinate. Ogni funzione qui sotto e' inerte quando `scenes` e' null.

function sceneOf(i) {
  if (!scenes) return -1;
  for (let s = 0; s < scenes.length; s++)
    if (i >= scenes[s].first_shot && i <= scenes[s].last_shot) return s;
  return -1;
}

function sceneCast(sc) {
  const n = {};
  for (let i = sc.first_shot; i <= sc.last_shot; i++)
    (shots[i].characters || []).forEach(id => n[id] = (n[id]||0) + 1);
  return Object.entries(n).sort((a,b) => b[1]-a[1]).slice(0,3)
    .map(([id]) => (castById[id]||{}).name).filter(Boolean);
}

function sceneLine(sc) {
  for (let i = sc.first_shot; i <= sc.last_shot; i++)
    if (shots[i].dialogue) return shots[i].dialogue;
  return '';
}

const nomeScena = (sc, si) => sc.name || `Scena ${String(si+1).padStart(2,'0')}`;

// I confini automatici sono giusti circa una volta su tre (F1 0,30 contro 0,63 di accordo fra
// annotatori umani): senza queste correzioni la struttura sarebbe da guardare e basta.
function mergeWithPrev(si) {
  if (si <= 0) return;
  ricorda();
  scenes[si-1].last_shot = scenes[si].last_shot;
  scenes.splice(si, 1);
  afterEdit(si - 1);
}

function splitAt(i) {            // lo shot `i` diventa l'inizio di una scena nuova
  const si = sceneOf(i);
  if (si < 0 || i <= scenes[si].first_shot) return;
  ricorda();
  scenes.splice(si + 1, 0, { index:0, first_shot:i, last_shot:scenes[si].last_shot,
                             start_frame:0, end_frame:0, start_time:0, end_time:0 });
  scenes[si].last_shot = i - 1;
  afterEdit(si + 1);
}

// Spostare un confine e' sempre una cosa a due: quello che una scena prende, la vicina lo perde.
// Le scene restano contigue per costruzione, quindi `checkScenes` non ha niente da dire — e
// nessuna delle due puo' restare vuota, che e' l'unico modo di rompere il contratto da qui.
function spostaInizio(si, d) {
  const sc = scenes[si], prec = scenes[si-1];
  if (!prec) return;                          // la prima scena parte da 0, per contratto
  const n = sc.first_shot + d;
  if (n <= prec.first_shot || n > sc.last_shot) return;
  ricorda();
  sc.first_shot = n; prec.last_shot = n - 1;
  afterEdit(si);
}

function spostaFine(si, d) {
  const sc = scenes[si], succ = scenes[si+1];
  if (!succ) return;                          // l'ultima finisce sull'ultimo shot, per contratto
  const n = sc.last_shot + d;
  if (n < sc.first_shot || n >= succ.last_shot) return;
  ricorda();
  sc.last_shot = n; succ.first_shot = n + 1;
  afterEdit(si);
}

// Eliminare una scena non elimina i suoi shot: li passa alla vicina, se no resterebbero scoperti.
function eliminaScena(si) {
  if (scenes.length < 2) return;
  ricorda();
  const sc = scenes[si];
  if (si > 0) scenes[si-1].last_shot = sc.last_shot;
  else scenes[1].first_shot = sc.first_shot;
  scenes.splice(si, 1);
  afterEdit(Math.max(0, si - 1));
}

function renumberScenes() {
  scenes.forEach((sc, i) => {
    sc.index = i;
    sc.start_frame = shots[sc.first_shot].start_frame;
    sc.end_frame   = shots[sc.last_shot].end_frame;
    sc.start_time  = shots[sc.first_shot].start_time;
    sc.end_time    = shots[sc.last_shot].end_time;
  });
  DATA.n_scenes = scenes.length;
  renderMeta();
  checkScenes();
}

// Le scene sono contigue e coprono tutti gli shot: e' lo stesso contratto dei range di frame nel
// resto del progetto, ed e' la classe di bug che qui si paga cara. Meglio in console che dentro
// un export silenziosamente rotto.
function checkScenes() {
  if (!scenes || !scenes.length) return true;
  let ok = scenes[0].first_shot === 0 && scenes[scenes.length-1].last_shot === shots.length - 1;
  scenes.forEach((sc, i) => {
    if (sc.last_shot < sc.first_shot) ok = false;
    if (i && sc.first_shot !== scenes[i-1].last_shot + 1) ok = false;
  });
  if (!ok) console.error('scene non contigue o non complete', scenes);
  return ok;
}

function afterEdit(si) {
  renumberScenes();
  open.clear(); open.add(si); scenaAperta = si;   // gli indici sono cambiati: il set vecchio non
                                                  // vuol piu' dire niente
  dirty();
  renderList($('filter').value.toLowerCase());
  renderTimeline();
  select(Math.min(Math.max(cur, 0), shots.length - 1));
}

function playScene(sc) {
  select(sc.first_shot);
  if (FILM) seekTo(sc, true);    // seekTo legge solo start_time/end_time: la scena e' uno shot lungo
  else if (shots[sc.first_shot].clip) {
    playing = { sc, i: sc.first_shot };
    $('player').play().catch(() => {});
  }
}

// clip su disco: la scena e' una playlist, si avanza a fine clip finche' si resta dentro
$('player').addEventListener('ended', () => {
  if (!playing || playing.i >= playing.sc.last_shot) { playing = null; return; }
  playing.i += 1;
  select(playing.i);
  $('player').play().catch(() => {});
});

// ------------------------------------------------------------------- shot ---
// Gli shot sono l'unico livello dove l'unita' e' il **frame**, non un indice: il confine lo
// detta la testina del player, non una riga della lista. Col film caricato `currentTime` e' gia'
// il tempo assoluto; solo ripiegando sulle clip l'offset e' lo start_frame dello shot — e li' il
// conto e' esatto solo con `--split-mode reencode`, perche' `copy` apre la clip al keyframe
// precedente e non c'e' modo di sapere da qui quanti frame ha in piu' in testa.

function frameBase() { const sh = shots[cur]; return !FILM && sh && sh.clip ? sh.start_frame : 0; }
function frameNow() { return frameBase() + Math.floor($('player').currentTime * DATA.fps); }

// Mezzo frame dentro: cosi' il `floor` di `frameNow` ridà esattamente `f` invece di inciampare
// sull'arrotondamento del confine.
function goToFrame(f) {
  const p = $('player'); p.pause();
  p.currentTime = (f - frameBase() + 0.5) / DATA.fps;
}

function renderFrame() {
  const sh = shots[cur], f = frameNow();
  // Il range accanto al frame non e' decorazione: il taglio deve cadere **dentro** lo shot e non
  // sul suo primo frame (li' non spezzerebbe niente), e i due modi di finirci fuori non si
  // vedono da soli — selezionare uno shot lascia la testina sul primo frame, e lasciar scorrere
  // la ferma a `end_time`, che e' **un frame oltre** l'ultimo. Senza il range il bottone sembra
  // spento a caso.
  $('frame').textContent = sh ? `frame ${f} · shot ${sh.start_frame}–${sh.end_frame}` : `frame ${f}`;
  $('split').disabled = !sh || f <= sh.start_frame || f > sh.end_frame;
  $('split').title = $('split').disabled
    ? 'porta la testina dentro lo shot (non sul primo frame) per poter tagliare'
    : `spezza lo shot: ${sh.start_frame}–${f-1} + ${f}–${sh.end_frame}`;
  $('mergeprev').disabled = cur <= 0;
}
$('player').addEventListener('timeupdate', renderFrame);
$('player').addEventListener('seeked', renderFrame);

// `end_frame` e' inclusivo (core/scene.py) e `end_time` e' `(end_frame + 1) / fps`: il frame `f`
// apre il secondo shot, quindi il primo si chiude a `f - 1` e i due tempi coincidono su `f/fps`.
function splitShotAt(f) {
  const sh = shots[cur];
  if (f <= sh.start_frame || f > sh.end_frame) return;
  ricorda();
  // Descrizione e dialogo vanno a **entrambi** i figli. Dopo un taglio manuale sono comunque da
  // rifare, ma perderli in silenzio e' il danno gia' pagato una volta (manifest.py,
  // CAMPI_COSTOSI). `thumb` e `clip` puntano ancora a quelli del padre: li rifa' il ritaglio.
  const nuovo = { ...sh, start_frame: f, end_frame: sh.end_frame,
                  start_time: f / DATA.fps, end_time: sh.end_time, confidence: null };
  delete nuovo.transition;          // la giunta apriva il padre, non il figlio
  sh.end_frame = f - 1;
  sh.end_time = f / DATA.fps;
  shots.splice(cur + 1, 0, nuovo);
  // gli indici a valle slittano di uno; la scena che conteneva `cur` ha uno shot in piu'
  if (scenes) scenes.forEach(sc => {
    if (sc.first_shot > cur) sc.first_shot++;
    if (sc.last_shot >= cur) sc.last_shot++;
  });
  afterShotEdit(cur + 1);
}

function mergeShotWithPrev(i) {
  if (i <= 0) return;
  ricorda();
  const a = shots[i-1], b = shots[i];
  a.end_frame = b.end_frame;
  a.end_time = b.end_time;
  const unisci = (x, y) => [x, y].filter(Boolean).join(' ');
  a.dialogue = unisci(a.dialogue, b.dialogue);
  a.description = unisci(a.description, b.description);
  a.characters = [...new Set([...(a.characters || []), ...(b.characters || [])])];
  if (a.speakers || b.speakers)
    a.speakers = [...new Set([...(a.speakers || []), ...(b.speakers || [])])];
  shots.splice(i, 1);
  if (scenes) {
    scenes.forEach(sc => {
      if (sc.first_shot > i) sc.first_shot--;
      if (sc.last_shot >= i) sc.last_shot--;
    });
    // fondere oltre il confine di scena puo' svuotare una scena fatta del solo shot `i`: va
    // tolta, altrimenti resta un range vuoto e `checkScenes` si lamenta a ragione
    for (let s = scenes.length - 1; s >= 0; s--)
      if (scenes[s].last_shot < scenes[s].first_shot) scenes.splice(s, 1);
  }
  afterShotEdit(i - 1);
}

function afterShotEdit(i) {
  shots.forEach((sh, k) => sh.index = k);
  DATA.n_shots = shots.length;
  if (scenes) renumberScenes(); else renderMeta();   // renumberScenes ridisegna gia' la meta
  dirty();
  renderList($('filter').value.toLowerCase());
  renderTimeline();
  select(Math.min(Math.max(i, 0), shots.length - 1));
}

// -------------------------------------------------------------- revisione ---
// Correggere 307 confini a occhio vuol dire riguardarsi tre ore e mezza. Ma il detector sa gia'
// dove ha dubitato: la confidenza e' il picco della giunta, e sotto 0,50 — misurato su *Anna*,
// `prove/annota_deboli.py` — quasi nessuna corsa e' uno stacco vero. Con `--min-peak 0.5` quelle
// corse non diventano confini, e la coda si riduce alle graduali. Le graduali entrano comunque:
// sono il posto dove i confini automatici sbagliano di piu', qualunque sia la confidenza.
const SOGLIA_DEBOLE = 0.5;
// Tre viste sullo stesso catalogo, non tre pagine: 'lista' (le scene), 'coda' (i confini da
// rivedere), 'scheda' (i numeri del film). Una variabile sola, perche' due booleani si possono
// accendere insieme e allora bisogna decidere chi vince.
let vista = 'lista';
const revisione = () => vista === 'coda';
let coda = [];

function daRivedere() {
  return shots.map((_, i) => i)
    .filter(i => !shots[i].rivisto
                 && ((shots[i].confidence != null && shots[i].confidence < SOGLIA_DEBOLE)
                     || !!shots[i].transition))
    .sort((a, b) => (shots[a].confidence ?? 1) - (shots[b].confidence ?? 1));
}

function perche(sh) {
  const p = [];
  if (sh.confidence != null && sh.confidence < SOGLIA_DEBOLE)
    p.push(sh.confidence.toFixed(2).replace('.', ','));
  if (sh.transition) p.push('graduale ' + sh.transition.n_frames + 'f');
  return p.join(' · ');
}

function mostraVista(v) {
  vista = vista === v ? 'lista' : v;          // ripremendo lo stesso bottone si torna alla lista
  $('rivedi').setAttribute('aria-pressed', vista === 'coda');
  $('rivedi').textContent = vista === 'coda' ? '✕ esci' : '⚑ rivedi';
  $('scheda').setAttribute('aria-pressed', vista === 'scheda');
  $('scheda').textContent = vista === 'scheda' ? '✕ esci' : '⊞ scheda';
  $('aiuto').setAttribute('aria-pressed', vista === 'aiuto');
  $('aiuto').textContent = vista === 'aiuto' ? '✕ esci' : '? aiuto';
  const pieno = vista === 'scheda' || vista === 'aiuto';
  $('pannello').hidden = !pieno;
  $('main').hidden = pieno;
  $('cast').hidden = pieno;                   // e' un filtro della lista: qui non filtra niente
  if (pieno) $('pannello').scrollTop = 0;
  renderFiltri();
  if (vista === 'scheda') return renderScheda();
  if (vista === 'aiuto') return renderAiuto();
  renderList($('filter').value.toLowerCase());
  if (vista === 'coda' && coda.length && !coda.includes(cur)) select(coda[0]);
}

// La coda si accorcia mentre lavori, quindi il passo si calcola sulla posizione **prima** del
// segno: dopo, `indexOf(cur)` non trova piu' niente e si tornerebbe sempre in cima.
function vaiInCoda(d) {
  if (!coda.length) return;
  const p = coda.indexOf(cur);
  select(coda[Math.min(Math.max((p < 0 ? 0 : p) + d, 0), coda.length - 1)]);
}

function segnaVisto() {
  if (!revisione() || cur < 0) return;
  ricorda();
  const p = Math.max(coda.indexOf(cur), 0);
  shots[cur].rivisto = true;
  dirty();
  const dopo = daRivedere();
  renderList($('filter').value.toLowerCase());
  if (dopo.length) select(dopo[Math.min(p, dopo.length - 1)]);
}

// ------------------------------------------------------------------ scheda ---
// I numeri ci sono gia' tutti nel manifest: qui non si calcola niente di nuovo, si legge. Una
// serie sola per ogni grafico, quindi un colore solo e nessuna legenda — e ogni barra porta il
// suo numero scritto, cosi' il dato si legge anche senza guardare la lunghezza.
const durata = sh => sh.end_time - sh.start_time;
const mediana = v => { const o = [...v].sort((a,b) => a-b);
                       return o.length ? o[Math.floor(o.length/2)] : 0; };
const mmss = s => `${Math.floor(s/60)}:${String(Math.round(s%60)).padStart(2,'0')}`;

function cifra(valore, etichetta) {
  return `<div class="cifra"><b>${valore}</b><span>${etichetta}</span></div>`;
}

function barre(righe, unita) {
  const max = Math.max(...righe.map(r => r.v), 1);
  return `<div class="barre">` + righe.map(r =>
    `<div class="barra"><span class="e" title="${esc(r.k)}">${esc(r.k)}</span>`
    + `<span class="p"><i style="width:${(100*r.v/max).toFixed(1)}%"></i></span>`
    + `<span class="n">${r.t ?? r.v}${unita || ''}</span></div>`).join('') + `</div>`;
}

function renderScheda() {
  const d = shots.map(durata), tot = DATA.duration || d.reduce((a,b) => a+b, 0);
  const grad = shots.filter(sh => sh.transition);
  const p = $('pannello');

  const bordi = [0, 1, 2, 4, 8, 16, 32, Infinity];
  const conte = bordi.slice(0, -1).map((a, i) => ({
    k: bordi[i+1] === Infinity ? 'oltre 32s' : `${a}–${bordi[i+1]}s`,
    v: d.filter(x => x >= a && x < bordi[i+1]).length }));

  // minuti in scena per personaggio: uno shot conta per ogni personaggio che ci compare
  const minuti = {};
  shots.forEach((sh, i) => (sh.characters || []).forEach(id => minuti[id] = (minuti[id] || 0) + d[i]));
  const perPers = Object.entries(minuti).sort((a,b) => b[1]-a[1]).slice(0, 12)
    .map(([id, sec]) => ({ k: (castById[id] || {}).name || ('Personaggio ' + id),
                           v: sec, t: mmss(sec) }));

  const maxD = Math.max(...d, 1);
  const ritmo = shots.map((sh, i) =>
    `<i style="left:${(100*sh.start_time/tot).toFixed(4)}%;`
    + `width:${Math.max(100*d[i]/tot, 0.05).toFixed(4)}%;`
    + `height:${(100*Math.sqrt(d[i]/maxD)).toFixed(1)}%" data-i="${i}"`
    + ` title="#${String(i).padStart(3,'0')}  ${fmt(sh.start_time)}  ${d[i].toFixed(1)}s"></i>`).join('');

  p.innerHTML = `
    <h2>Il film</h2>
    <div class="cifre">
      ${cifra(fmt(tot), 'durata')}
      ${cifra(shots.length, 'shot')}
      ${cifra(scenes ? scenes.length : '—', 'scene')}
      ${cifra((tot/shots.length).toFixed(1) + 's', 'ASL (durata media)')}
      ${cifra(mediana(d).toFixed(1) + 's', 'durata mediana')}
      ${cifra(grad.length, 'transizioni graduali')}
    </div>
    <h2>Ritmo del montaggio — ogni barra e' uno shot, l'altezza e' la sua durata</h2>
    <div id="ritmo">${ritmo}</div>
    <div class="assex"><span>0:00</span><span>${fmt(tot/2)}</span><span>${fmt(tot)}</span></div>
    <h2>Quanti shot per durata</h2>
    ${barre(conte, ' shot')}
    <h2>Minuti in scena per personaggio${perPers.length ? '' : ' — nessun volto riconosciuto'}</h2>
    ${perPers.length ? barre(perPers) : ''}`;

  p.querySelectorAll('#ritmo i').forEach(b => b.onclick = () => {
    mostraVista('lista');
    select(+b.dataset.i);
  });
}

// ------------------------------------------------------------------- aiuto ---
// Sta dentro la pagina e non in un file accanto: un catalogo si sposta, si copia su una chiavetta
// e si manda a qualcuno, e le istruzioni devono venire con lui. Il costo e' qualche kB di testo.
const tasti = [
  ['↑ ↓  ·  J K', 'shot precedente / successivo. Con un filtro acceso salta al prossimo che lo soddisfa; in <b>rivedi</b> scorre la coda'],
  ['← →', 'un fotogramma indietro / avanti'],
  ['spazio', 'play e pausa'],
  ['S', 'taglia lo shot al fotogramma sul player'],
  ['M', 'unisci questo shot al precedente'],
  ['D', 'apri e chiudi il dialogo'],
  ['E', 'apri e chiudi la descrizione'],
  ['R', 'entra ed esci da <b>rivedi</b>'],
  ['V', 'in <b>rivedi</b>: segna il confine come visto e passa al prossimo'],
  ['T', 'entra ed esci dalla <b>scheda</b>'],
  ['H', 'questa pagina'],
  ['⌘Z  ·  Ctrl Z', "annulla l'ultima modifica di struttura"],
];

function renderAiuto() {
  $('pannello').innerHTML = `
  <div class="aiuto">
    <section>
    <h2>Cos'e' questa pagina</h2>
    <p>Il catalogo di <b>${esc(DATA.video || 'un film')}</b>: ${DATA.n_shots} shot rilevati da
    <b>${esc(DATA.detector || '?')}</b>${scenes ? `, raggruppati in ${scenes.length} scene` : ''}.
    E' un file solo e funziona col doppio clic, senza rete e senza server. Le correzioni che fai
    restano nel browser; per portarle fuori c'e' il menu <b>↓ esporta</b>.</p>

    </section>
    <section>
    <h2>Le quattro viste</h2>
    <ul>
      <li><b>lista</b> — le scene con dentro gli shot, e a destra il player dello shot scelto.</li>
      <li><b>⚑ rivedi</b> — solo i confini su cui il detector ha dubitato, dal piu' incerto.
      Ci finiscono gli shot con confidenza sotto ${String(SOGLIA_DEBOLE).replace('.', ',')} e
      tutte le transizioni graduali. Si smaltisce con <kbd>↑</kbd><kbd>↓</kbd> e <kbd>V</kbd>.</li>
      <li><b>⊞ scheda</b> — i numeri del film: durata media degli shot, ritmo del montaggio,
      quanti shot per durata, minuti in scena per personaggio. Le barre del ritmo sono cliccabili.</li>
      <li><b>? aiuto</b> — questa.</li>
    </ul>

    </section>
    <section>
    <h2>Il player</h2>
    <p><b>◀ 1f</b> e <b>1f ▶</b> muovono di un fotogramma; <b>⏪ 5s</b> e <b>5s ⏩</b> saltano cinque
    secondi <span class="nota">e attraversano i confini dello shot, seguendo la timeline</span>.
    La velocita' (0,25× → 2×) resta quella che scegli anche cambiando shot, e l'audio non cambia
    tono. <b>⏹ stop a fine shot</b> e' spento di default: acceso, la riproduzione si ferma
    sull'<b>ultimo fotogramma</b> dello shot invece di proseguire.</p>

    </section>
    <section>
    <h2>Correggere i confini degli shot</h2>
    <p><b>✂ taglia qui</b> spezza lo shot al fotogramma che vedi: quello diventa il primo del
    nuovo. E' spento se la testina sta sul primo fotogramma dello shot (li' non spezzerebbe
    niente) o se e' uscita oltre la fine — accanto al numero c'e' sempre il range dello shot, per
    capire quale dei due casi e'. <b>⤴ unisci al prec</b> rifonde questo shot nel precedente.</p>
    <p class="nota">Il numero del fotogramma e' contato <b>sul film</b>, non sulla clip: e' esatto
    a prescindere da come sono state tagliate le clip su disco.</p>

    </section>
    <section>
    <h2>Le scene</h2>
    <p>I comandi compaiono sulla scena dove stai lavorando: <b>⤴ unisci</b> alla precedente,
    <b>✂ dividi</b> per farne una nuova a partire dallo shot corrente, <b>✎</b> per rinominarla
    <span class="nota">(Invio conferma, Esc annulla, vuoto torna al nome di default)</span>,
    <b>inizio ◀ ▶</b> e <b>fine ◀ ▶</b> per spostare un confine di uno shot, <b>✕</b> per
    eliminarla. Eliminare una scena non elimina i suoi shot: passano alla vicina.</p>

    </section>
    <section>
    <h2>I personaggi</h2>
    <p>La striscia in alto e' il cast: il nome si scrive sopra la miniatura, e cliccando una
    faccia la lista mostra solo i suoi shot.</p>
    <p>Il raggruppamento dei volti sbaglia soprattutto in un verso: <b>spezza</b> una persona in
    due gruppi, per un profilo, un cappello, una luce diversa. Il pulsante <b>⇄</b> su una
    miniatura serve a rimetterli insieme: il primo clic sceglie chi sparisce, il secondo su
    un'altra faccia dice in chi confluisce. <kbd>Esc</kbd> lascia perdere, <kbd>⌘Z</kbd> annulla
    anche una fusione gia' fatta.</p>
    <p class="nota">Un gruppo con <b>⚠</b> non e' stato riconosciuto come volto umano: li' dentro
    possono esserci persone diverse, e quel nome non finisce nelle descrizioni.</p>

    <h2>Dialogo e descrizione</h2>
    <p>Stanno chiusi e si aprono col loro titolo, o con <kbd>D</kbd> e <kbd>E</kbd>. Chiusi
    mostrano l'inizio del testo. Sono caselle: quello che scrivi e' la correzione, e finisce
    nell'export.</p>

    </section>
    <section>
    <h2>Cercare e filtrare</h2>
    <p>Due caselle di ricerca in testa: una cerca nei <b>dialoghi</b>, l'altra nelle
    <b>descrizioni</b>. Si possono usare insieme.</p>
    <p>Sei interruttori sopra la lista, che si sommano fra loro e con le due ricerche.
    A destra il contatore dice quanti shot restano. Con un filtro acceso le frecce saltano
    direttamente al prossimo shot che lo soddisfa.</p>

    </section>
    <section>
    <h2>Salvataggio</h2>
    <p>Ogni modifica finisce nel browser <b>400 ms dopo che smetti di scrivere</b> — non ogni
    tot minuti: se chiudi la scheda per sbaglio, riaprendola ritrovi tutto e la pagina te lo dice,
    con un <b>scarta</b> accanto per buttare la copia e ripartire da com'e' su disco.</p>
    <p>Se pero' rigeneri il catalogo e i confini si spostano, la copia nel browser non viene
    ripescata: parlerebbe di shot che non esistono piu'.</p>
    <p><b>↶ annulla</b> (<kbd>⌘Z</kbd>) torna indietro di venti passi sulle modifiche di
    struttura — tagli, unioni, confini di scena, nomi, «visto». Il testo dentro le caselle lo
    annulla il browser.</p>
    <p class="nota">Niente di tutto questo tocca <b>manifest.json</b>: una pagina aperta col
    doppio clic non puo' scrivere su disco.</p>

    </section>
    <section>
    <h2>Portare fuori il lavoro</h2>
    <p>Tutto dal menu <b>↓ esporta</b> in testa:</p>
    <ul>
      <li><b>JSON</b> — il catalogo corretto. E' il file da rimandare indietro, e quello che
      rilegge la pipeline con <span class="nota">--from-manifest</span> per ritagliare le clip
      dai confini giusti.</li>
      <li><b>EDL</b> — lista di montaggio CMX3600 coi confini al fotogramma, che Premiere e
      Resolve aprono.</li>
      <li><b>SRT</b> — sottotitoli dai dialoghi. Sono lunghi quanto lo shot: e' un trascritto,
      non sottotitoli da messa in onda.</li>
    </ul>

    </section>
    <section>
    <h2>Due cose che si pagano care</h2>
    <ul>
      <li>L'identita' di uno shot e' il suo <b>fotogramma d'inizio</b>, non il numero in lista:
      un taglio sposta di uno tutti i numeri a valle. Per questo un nome o un «visto» non tornano
      su un confine che si e' mosso — e' il comportamento giusto, parlavano di un altro pezzo.</li>
      <li>Il fotogramma finale di uno shot e' <b>compreso</b>. Il primo dello shot dopo e' quello
      successivo, senza buchi.</li>
    </ul>

    </section>
    <section class="largo">
    <h2>Scorciatoie</h2>
    <div class="tasti">${tasti.map(([k, t]) =>
      `<div><span>${k.split('  ').map(x => x === '·' ? x : `<kbd>${x}</kbd>`).join(' ')}</span>`
      + `<span>${t}</span></div>`).join('')}</div>
    <p class="nota" style="margin-top:.8rem">Le lettere non funzionano mentre scrivi in una
    casella di testo.</p>
    </section>
  </div>`;
}

// ------------------------------------------------------------------ filtri ---
// Sei domande che si fanno sempre e che a mano vogliono dire scorrere 307 righe. Si sommano fra
// loro e col testo cercato: sono tutte condizioni *and*, perche' servono a stringere.
const FILTRI = {
  'senza descrizione': sh => !sh.description,
  'senza dialogo':     sh => !sh.dialogue,
  'con transizione':   sh => !!sh.transition,
  'incerto':           sh => sh.confidence != null && sh.confidence < SOGLIA_DEBOLE,
  'breve <1s':         sh => (sh.end_time - sh.start_time) < 1,
  'lungo >30s':        sh => (sh.end_time - sh.start_time) > 30,
};
const attivi = new Set();

function mostrato(i, filter = $('filter').value.toLowerCase()) {
  const sh = shots[i];
  const descr = $('filterDescr').value.toLowerCase();
  if (filter && !(sh.dialogue || '').toLowerCase().includes(filter)) return false;
  if (descr && !(sh.description || '').toLowerCase().includes(descr)) return false;
  if (charFilter !== null && !(sh.characters || []).includes(charFilter)) return false;
  for (const k of attivi) if (!FILTRI[k](sh)) return false;
  return true;
}

const filtrando = () =>
  attivi.size || $('filter').value || $('filterDescr').value || charFilter !== null;

function renderFiltri() {
  const box = $('filtri');
  box.className = vista === 'lista' ? '' : 'spento';
  box.innerHTML = '';
  const l = document.createElement('span'); l.className = 'lab'; l.textContent = 'mostra solo';
  box.appendChild(l);
  Object.keys(FILTRI).forEach(k => {
    const b = actBtn(k, `solo gli shot: ${k}`, () => {
      attivi.has(k) ? attivi.delete(k) : attivi.add(k);
      renderFiltri();
      renderList($('filter').value.toLowerCase());
    });
    b.setAttribute('aria-pressed', attivi.has(k));
    box.appendChild(b);
  });
  const n = document.createElement('span');
  n.id = 'quanti';
  const quanti = shots.filter((_, i) => mostrato(i)).length;
  n.textContent = filtrando() ? `${quanti} shot su ${shots.length}` : `${shots.length} shot`;
  box.appendChild(n);
}

// Con un filtro attivo le frecce saltano al prossimo che lo soddisfa: scorrere trenta righe
// nascoste per arrivare alla successiva visibile e' esattamente il lavoro che il filtro toglie.
function passa(d) {
  if (!filtrando()) return select(cur + d);
  let i = cur + d;
  while (i >= 0 && i < shots.length && !mostrato(i)) i += d;
  if (i >= 0 && i < shots.length) select(i);
}

// ------------------------------------------------------------------ lista ---

// In revisione la lista e' piatta: la struttura in scene non serve, serve la fila da smaltire.
function renderCoda(list) {
  coda = daRivedere();
  const visti = shots.filter(sh => sh.rivisto).length;
  const testa = document.createElement('div');
  testa.id = 'coda';
  testa.innerHTML = coda.length
    ? `<b>${coda.length}</b> confini da rivedere` + (visti ? ` · ${visti} gia' visti` : '')
      + ` · <span>V segna visto, ↑↓ scorre</span>`
    : `<b>nessun confine incerto</b>` + (visti ? ` · ${visti} visti` : '');
  list.appendChild(testa);
  coda.forEach(i => {
    const row = shotRow(i);
    const p = perche(shots[i]);
    if (p) row.querySelector('.h').insertAdjacentHTML('beforeend', `<span class="perche">${p}</span>`);
    list.appendChild(row);
  });
}

function shotRow(i) {
  const sh = shots[i], d = sh.dialogue || '';
  const el = document.createElement('div');
  el.className = 'item' + (i===cur ? ' sel' : '');
  el.dataset.i = i;
  // la miniatura c'e' solo con `--scenes` (le estrae quello step): senza, la riga resta di testo
  el.innerHTML = (sh.thumb ? `<img src="${encodeURI(sh.thumb)}" alt="" loading="lazy">` : '')
               + `<div class="c"><div class="h"><span>#${String(i).padStart(3,'0')}</span>`
               + `<span>${fmt(sh.start_time)}–${fmt(sh.end_time)}</span></div>`
    // col trattino "nessun dialogo" la riga cresce di 16px per non dire niente: con la
    // miniatura il vuoto si vede gia'
               + (d && forzaDlg ? `<div class="d">${esc(d.slice(0,120))}</div>`
                                : (sh.thumb || d ? '' : '<div class="d"><i>—</i></div>')) + `</div>`;
  el.onclick = () => { playing = null; select(i); };
  return el;
}

function sceneHeader(sc, si, n) {
  const th = shots[sc.first_shot].thumb;
  const who = sceneCast(sc), line = sceneLine(sc);
  const el = document.createElement('div');
  el.className = 'sh';
  el.innerHTML = `<span class="chev">${open.has(si) ? '▾' : '▸'}</span>`
    + (th ? `<img src="${encodeURI(th)}" alt="" loading="lazy">` : '')
    + `<div class="b"><div class="t"><span class="nome">${esc(nomeScena(sc, si))}</span>`
    + `<span>${fmt(sc.start_time)}–${fmt(sc.end_time)}</span></div>`
    + `<div class="who">${n} shot${who.length ? ' · ' + esc(who.join(', ')) : ''}</div>`
    + (forzaDlg && line ? `<div class="d">${esc(line.slice(0,90))}</div>` : '')
    + `<div class="acts"></div></div>`;
  el.querySelector('.nome').ondblclick = e => { e.stopPropagation(); rinomina(el, sc, si); };
  el.querySelector('.chev').onclick = e => {
    e.stopPropagation();
    open.has(si) ? open.delete(si) : open.add(si);
    scenaAperta = si;                 // decisione presa a mano: `select` la rispetta
    renderList($('filter').value.toLowerCase());
  };
  const acts = el.querySelector('.acts');
  const sh_ = i => '#' + String(i).padStart(3,'0');
  if (si > 0) acts.appendChild(actBtn('⤴ unisci', 'unisci alla scena precedente', () => mergeWithPrev(si)));
  if (cur > sc.first_shot && cur <= sc.last_shot)
    acts.appendChild(actBtn('✂ dividi', `nuova scena a partire da ${sh_(cur)}`, () => splitAt(cur)));
  acts.appendChild(actBtn('✎', 'rinomina (Invio conferma, Esc annulla)', () => rinomina(el, sc, si)));
  // Ogni confine e' condiviso con la scena vicina: la prima non ha un inizio da spostare e
  // l'ultima non ha una fine, per contratto.
  if (si > 0)
    acts.appendChild(gruppo('inizio',
      actBtn('◀', `l'inizio arretra a ${sh_(sc.first_shot-1)} (lo prende alla scena prima)`,
             () => spostaInizio(si, -1)),
      actBtn('▶', `l'inizio avanza a ${sh_(sc.first_shot+1)} (lo cede alla scena prima)`,
             () => spostaInizio(si, +1))));
  if (si < scenes.length - 1)
    acts.appendChild(gruppo('fine',
      actBtn('◀', `la fine arretra a ${sh_(sc.last_shot-1)} (lo cede alla scena dopo)`,
             () => spostaFine(si, -1)),
      actBtn('▶', `la fine avanza a ${sh_(sc.last_shot+1)} (lo prende alla scena dopo)`,
             () => spostaFine(si, +1))));
  if (scenes.length > 1)
    acts.appendChild(actBtn('✕', 'elimina la scena: i suoi shot passano alla vicina',
                            () => eliminaScena(si)));
  el.onclick = () => playScene(sc);
  return el;
}

function gruppo(testo, ...bottoni) {
  const g = document.createElement('span');
  g.className = 'gruppo';
  const l = document.createElement('span'); l.className = 'lab'; l.textContent = testo;
  g.appendChild(l);
  bottoni.forEach(b => g.appendChild(b));
  return g;
}

// Modifica in linea, nel posto dove il nome si legge: niente finestre, niente menu. `blur`
// conferma come Invio, ma `fatto` impedisce il secondo giro — chiudere ridisegna la lista, e il
// ridisegno stacca l'input, che sparendo emette a sua volta un `blur`.
function rinomina(el, sc, si) {
  const span = el.querySelector('.nome');
  if (!span || span.querySelector('input')) return;
  const inp = document.createElement('input');
  inp.className = 'rinomina';
  inp.value = sc.name || '';
  inp.placeholder = nomeScena(sc, si);
  span.textContent = '';
  span.appendChild(inp);
  inp.focus(); inp.select();
  let fatto = false;
  const chiudi = salva => {
    if (fatto) return;
    fatto = true;
    if (salva) {
      ricorda();
      const v = inp.value.trim();
      if (v) sc.name = v; else delete sc.name;      // vuoto: torna al nome di default
      dirty();
    }
    renderList($('filter').value.toLowerCase());
  };
  inp.onclick = inp.ondblclick = e => e.stopPropagation();
  inp.onkeydown = e => {
    e.stopPropagation();
    if (e.key === 'Enter')  { e.preventDefault(); chiudi(true); }
    if (e.key === 'Escape') { e.preventDefault(); chiudi(false); }
  };
  inp.onblur = () => chiudi(true);
}

function actBtn(label, title, fn) {
  const b = document.createElement('button');
  b.textContent = label; b.title = title;
  b.onclick = e => { e.stopPropagation(); fn(); };
  return b;
}

function renderList(filter='') {
  const list = $('list');
  // `innerHTML=''` azzera `scrollTop`: senza rimetterlo, ogni ridisegno riporta la lista in cima
  // e `scrollIntoView` la riporta giu', due passaggi di layout che si vedono
  const scorso = list.scrollTop;
  list.innerHTML = '';
  if (revisione()) { renderCoda(list); list.scrollTop = scorso; return; }
  const shown = i => mostrato(i, filter);
  forzaDlg = !!filter || charFilter !== null;
  if (!scenes) {
    shots.forEach((_, i) => { if (shown(i)) list.appendChild(shotRow(i)); });
    list.scrollTop = scorso;
    return;
  }

  // `filtrando()`, non solo il testo: con un filtro attivo le scene si aprono da sole, se no il
  // contatore dice «48 shot su 307» e la lista mostra solo intestazioni di scena chiuse.
  const filtering = filtrando();
  forzaDlg = !!filter || charFilter !== null;   // il brano nella riga serve solo cercando testo
  scenes.forEach((sc, si) => {
    const kids = [];
    for (let i = sc.first_shot; i <= sc.last_shot; i++) if (shown(i)) kids.push(i);
    if (!kids.length) return;                       // scena senza superstiti: sparisce dal filtro
    // col filtro attivo si espande: nascondere i risultati dentro scene chiuse sarebbe assurdo
    const isOpen = open.has(si) || filtering;
    const box = document.createElement('div');
    box.className = 'scene' + (isOpen ? ' open' : '') + (sceneOf(cur) === si ? ' cur' : '');
    box.appendChild(sceneHeader(sc, si, kids.length));
    // le righe di una scena chiusa non si costruiscono: `select` ridisegna la lista a ogni
    // spostamento, e su 3200 shot crearle tutte a ogni freccia si sente
    if (isOpen) {
      const inner = document.createElement('div');
      inner.className = 'shots';
      kids.forEach(i => inner.appendChild(shotRow(i)));
      box.appendChild(inner);
    }
    list.appendChild(box);
  });
  list.scrollTop = scorso;
}

function renderTimeline() {
  const track = $('track'), bands = $('bands');
  track.querySelectorAll('.pin').forEach(e => e.remove());   // ridisegnata dopo ogni modifica
  bands.innerHTML = '';
  const total = DATA.duration || (shots.length ? shots[shots.length-1].end_time : 0);
  if (!total) return;
  if (scenes) scenes.forEach((sc, si) => {
    const b = document.createElement('div');
    b.className = 'band' + (si % 2 ? ' alt' : '');
    b.dataset.s = si;
    b.style.left = (100 * sc.start_time / total) + '%';
    b.style.width = (100 * (sc.end_time - sc.start_time) / total) + '%';
    b.title = `Scena ${String(si+1).padStart(2,'0')}  ${fmt(sc.start_time)}–${fmt(sc.end_time)}`;
    b.onclick = () => playScene(sc);
    bands.appendChild(b);
  });
  shots.forEach((sh, i) => {
    const pin = document.createElement('div');
    pin.className = 'pin';
    pin.dataset.i = i;
    pin.style.left = (100 * sh.start_time / total) + '%';
    pin.title = `#${String(i).padStart(3,'0')}  ${fmt(sh.start_time)}–${fmt(sh.end_time)}` + (sh.dialogue ? '  ' + sh.dialogue.slice(0,60) : '');
    pin.onclick = () => { playing = null; select(i); };
    track.appendChild(pin);
  });
}

function select(i) {
  if (i < 0 || i >= shots.length) return;
  cur = i;
  const sh = shots[i];
  // Film disponibile: seek su quello gia' caricato, e i frame contati tornano. Solo senza,
  // una src per shot dalle clip su disco.
  if (FILM) seekTo(sh);
  else if (sh.clip) { stopAt = Infinity; $('player').src = sh.clip; }
  $('tc').textContent = `#${String(i).padStart(3,'0')}  ${fmt(sh.start_time)}–${fmt(sh.end_time)}  (${!FILM && sh.clip ? sh.clip : DATA.video})`;
  renderFrame();                 // il `seeked` arriva dopo: intanto i bottoni dicono il vero
  renderChips(sh);
  // `--diarize` è opt-in: senza, `speakers` non c'è e l'etichetta resta quella di sempre. Gli id
  // sono numeri perché la diarizzazione non sa i nomi — il linking speaker↔personaggio non c'è
  // ancora (plan/VERBALE.md §7).
  const spk = sh.speakers || [];
  etichettaTendina('dlgLabel', dlgAperto,
    spk.length ? `Dialogo · parlanti ${spk.map(s => 'S' + s).join(', ')}` : 'Dialogo', sh.dialogue);
  etichettaTendina('descrLabel', descrAperto, 'Descrizione', sh.description);
  $('dialogue').value = sh.dialogue || '';
  $('description').value = sh.description || '';
  const si = sceneOf(i);
  // La lista si ridisegna se cambia cosa deve mostrare: scena da aprire, o pulsante dividi da
  // spostare sulla scena corrente. **In revisione non cambia niente**: la coda e' la stessa fila
  // e spostarsi dentro sposta solo l'evidenziazione — ridisegnarla a ogni freccia faceva
  // *tremare* la finestra, perche' `innerHTML=''` azzera lo scroll e `scrollIntoView` lo rimette.
  if (!revisione() && scenes && si >= 0) {
    if (si !== scenaAperta) { open.add(si); scenaAperta = si; }
    renderList($('filter').value.toLowerCase());
  }
  document.querySelectorAll('.item').forEach(e => e.classList.toggle('sel', +e.dataset.i === i));
  document.querySelectorAll('.pin').forEach(e => e.classList.toggle('active', +e.dataset.i === i));
  document.querySelectorAll('.band').forEach(e => e.classList.toggle('cur', +e.dataset.s === si));
  const sel = document.querySelector('.item.sel'); if (sel) sel.scrollIntoView({block:'nearest'});
}

$('dialogue').addEventListener('input', e => { if (cur>=0) { shots[cur].dialogue = e.target.value; dirty(); }});
$('description').addEventListener('input', e => { if (cur>=0) { shots[cur].description = e.target.value; dirty(); }});
function dirty(){ $('saved').textContent = '● modifiche non esportate'; salvaLocale(); }

// ------------------------------------------------------ salva e annulla ---
// Le correzioni vivevano **solo** in questa scheda: chiudere la finestra per sbaglio costava
// l'ora di lavoro appena fatta, e l'unico avviso era «● modifiche non esportate». Qui si tengono
// anche nel browser. Non sostituisce l'export — il JSON su disco resta l'unica copia che
// sopravvive a un altro browser o a un altro computer — ma toglie il modo piu' stupido di
// perdere tutto.
const CHIAVE = 'scene-detector:' + (DATA.video || 'catalogo');
// Nel browser si salvano le **differenze** dal manifest arrivato da disco, non una copia intera.
// La copia intera copriva tutto quello che un run successivo aveva aggiunto sugli stessi confini:
// dopo un `--vlm` la pagina ripescava gli shot di prima, senza descrizioni, e un export seguito da
// `--from-manifest` le buttava davvero. Cosi' si riporta solo cio' che si fa a mano — confini,
// testi corretti, `rivisto`, nomi, fusioni — sopra quello che la pipeline ha calcolato nel frattempo.
const BASE = JSON.parse(JSON.stringify(DATA));
// L'identita' di uno shot e' il suo range, come in `merge_prior`: con lo stesso inizio e un'altra
// fine e' un altro pezzo di film.
const range = sh => sh.start_frame + '-' + sh.end_frame;
// Le impronte dicono se il run nuovo ha rifatto la parte su cui le modifiche si appoggiano. I
// confini del detector: se si sono mossi il ripescaggio non avviene, le modifiche parlerebbero di
// shot che non esistono piu'. Il cast: un `--faces` rifatto da capo cambia cosa vuol dire ogni id.
const impronta = DATA.fps + ':' + BASE.shots.map(range).join(',');
const improntaCast = (BASE.cast || []).map(c => c.id).join(',');
const improntaScene = JSON.stringify((BASE.scenes || []).map(sc => [sc.first_shot, sc.last_shot]));
const A_MANO = ['description', 'dialogue', 'characters', 'rivisto'];   // i campi che la UI modifica
let attesa = null;

function differenze() {
  const base = {}; BASE.shots.forEach(sh => base[range(sh)] = sh);
  const baseCast = {}; (BASE.cast || []).forEach(c => baseCast[c.id] = c);
  const uguali = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  return {
    versione: 2, impronta, improntaCast, improntaScene,
    shots: shots.map(sh => {
      const b = base[range(sh)];
      if (!b) return { ...sh, aMano: true };     // confine tagliato o unito qui: lo shot intero
      const d = { start_frame: sh.start_frame, end_frame: sh.end_frame };
      A_MANO.forEach(k => { if (!uguali(sh[k], b[k])) d[k] = sh[k] ?? null; });
      return d;
    }),
    scenes,
    // rinomine, e il conteggio rifatto dopo una fusione
    castMod: Object.fromEntries(cast
      .filter(c => { const b = baseCast[c.id] || {}; return c.name !== b.name || c.n_shots !== b.n_shots; })
      .map(c => [c.id, { name: c.name, n_shots: c.n_shots }])),
    tolti: (BASE.cast || []).map(c => c.id).filter(id => !castById[id]),   // fusi in un altro
  };
}

function salvaLocale() {
  clearTimeout(attesa);                 // digitando in un dialogo `dirty` parte a ogni tasto
  attesa = setTimeout(() => {
    try {
      localStorage.setItem(CHIAVE, JSON.stringify(differenze()));
    } catch (e) {
      // quota piena, o `localStorage` negato (finestra privata, file:// su certi browser).
      // Dirlo: lasciar credere che sia al sicuro e' peggio che non salvare.
      $('saved').textContent = '● NON salvate nel browser — esporta il JSON';
    }
  }, 400);
}

function ripescaLocale() {
  let v;
  try { v = JSON.parse(localStorage.getItem(CHIAVE) || 'null'); } catch (e) { return false; }
  if (!v) return false;
  if (v.versione !== 2) return ripescaCopiaIntera(v);
  if (v.impronta !== impronta) return false;          // il detector ha spostato i confini
  const castUguale = v.improntaCast === improntaCast;
  const nuovi = {}; shots.forEach(sh => nuovi[range(sh)] = sh);
  const rifatti = v.shots.map(d => {
    if (d.aMano) {
      const { aMano, ...sh } = d;
      if (!castUguale) sh.characters = [];            // id di un raggruppamento che non c'e' piu'
      return sh;
    }
    const sh = { ...nuovi[range(d)] };                 // c'e' per forza: stessa impronta
    A_MANO.forEach(k => { if (k in d && (castUguale || k !== 'characters')) sh[k] = d[k]; });
    return sh;
  });
  shots.splice(0, shots.length, ...rifatti);
  if (scenes && v.scenes) {
    // Le scene salvate valgono se il raggruppamento non e' stato rifatto, oppure se i confini
    // degli shot li hai cambiati tu: allora sono le sole coi `first_shot` giusti. Se no restano
    // quelle nuove, e dei tuoi ritocchi tornano i nomi, per `start_frame` come in `merge_scene_names`.
    if (v.shots.some(d => d.aMano) || v.improntaScene === improntaScene)
      scenes.splice(0, scenes.length, ...v.scenes);
    else {
      const nomi = {}; v.scenes.forEach(sc => { if (sc.name) nomi[sc.start_frame] = sc.name; });
      scenes.forEach(sc => { if (!sc.name && nomi[sc.start_frame]) sc.name = nomi[sc.start_frame]; });
    }
  }
  if (castUguale) {
    (v.tolti || []).forEach(id => {
      const i = cast.findIndex(c => c.id === id);
      if (i >= 0) cast.splice(i, 1);
      delete castById[id];
    });
    Object.entries(v.castMod || {}).forEach(([id, m]) => { if (castById[id]) Object.assign(castById[id], m); });
  }
  // i conteggi in testa vivono in `DATA`, non negli array: senza questo la riga diceva «6 shot»
  // con sette shot in lista, e sarebbero i numeri a sembrare rotti invece del ripescaggio
  DATA.n_shots = shots.length;
  if (scenes) DATA.n_scenes = scenes.length;
  return true;
}

// Salvataggi di prima delle differenze: una copia intera, rimessa com'era, con la sua impronta
// vecchia. Buttarli perderebbe modifiche mai esportate; il prossimo salvataggio li riscrive nel
// formato nuovo, quindi questo ramo serve una volta sola.
function ripescaCopiaIntera(v) {
  const vecchia = [DATA.n_shots, DATA.fps, shots.length && shots[0].start_frame,
                   shots.length && shots[shots.length-1].start_frame].join('/');
  if (v.impronta !== vecchia) return false;
  shots.splice(0, shots.length, ...v.shots);
  if (scenes && v.scenes) scenes.splice(0, scenes.length, ...v.scenes);
  (v.cast || []).forEach(c => { if (castById[c.id]) castById[c.id].name = c.name; });
  DATA.n_shots = shots.length;
  if (scenes) DATA.n_scenes = scenes.length;
  return true;
}

// Tagliare, unire ed eliminare sono distruttivi e non c'era modo di tornare indietro. Istantanee
// solo della **struttura**: dentro le textarea l'annulla ce l'ha gia' il browser.
const passato = [];
function ricorda() {
  passato.push(JSON.stringify({ shots, scenes, cast }));
  if (passato.length > 20) passato.shift();   // su 3204 shot ognuna pesa: venti bastano
}

function annulla() {
  const v = passato.pop();
  if (!v) return;
  const p = JSON.parse(v);
  shots.splice(0, shots.length, ...p.shots);
  if (scenes && p.scenes) scenes.splice(0, scenes.length, ...p.scenes);
  if (p.cast) {
    // gli oggetti tornano dal JSON, quindi sono **altri** oggetti: `castById` va rifatto, se no
    // punta a quelli di prima e il personaggio ripescato non ha nome da nessuna parte
    cast.splice(0, cast.length, ...p.cast);
    Object.keys(castById).forEach(k => delete castById[k]);
    cast.forEach(c => castById[c.id] = c);
    renderCast();
  }
  afterShotEdit(Math.min(cur, shots.length - 1));       // rinumera, ridisegna e risalva
  $('saved').textContent = '● annullato — modifiche non esportate';
}

// --------------------------------------------------------- riproduzione ---
$('player').preservesPitch = true;             // e' gia' il default: qui perche' a 0,25x e 2x il
                                               // parlato deve restare comprensibile
$('speed').onchange = e => {
  const p = $('player'), v = +e.target.value;
  // `defaultPlaybackRate` non e' ridondante: caricare una src nuova (i cataloghi vecchi, con le
  // clip) rimette `playbackRate` a quel valore, e senza la velocita' si azzererebbe a ogni shot.
  p.playbackRate = p.defaultPlaybackRate = v;
};

// Il salto attraversa i confini: la testina segue la timeline, non lo shot. Il `seeked` qui sopra
// disarma `stopAt` appena si finisce fuori, quindi non ripausa a sorpresa.
const salta = d => {
  const p = $('player');
  p.currentTime = Math.max(0, Math.min(p.duration || Infinity, p.currentTime + d));
};
$('back5').onclick = () => salta(-5);
$('fwd5').onclick = () => salta(5);

$('stopend').onclick = () => {
  stopShot = !stopShot;
  $('stopend').setAttribute('aria-pressed', stopShot);
  // Vale subito, senza riselezionare lo shot — ma solo se la testina e' ancora dentro: piu'
  // avanti, armare vorrebbe dire pausare e saltare all'indietro appena premuto il pulsante.
  const sh = shots[cur];
  stopAt = stopShot && sh && $('player').currentTime < sh.end_time ? sh.end_time : Infinity;
};

// Chiusa, la tendina non e' muta: mostra l'inizio del testo, cosi' si sa se c'e' qualcosa senza
// doverla aprire.
function etichettaTendina(bottone, aperto, testo, valore) {
  $(bottone).textContent = (aperto ? '▾ ' : '▸ ') + testo
    + (!aperto && valore ? ` · ${valore.slice(0, 46)}…` : '');
}

function apriTendina(campo, on) {
  if (campo === 'dialogue') dlgAperto = on; else descrAperto = on;
  $(campo).hidden = !on;
  $(campo === 'dialogue' ? 'dlgLabel' : 'descrLabel').setAttribute('aria-expanded', on);
  if (cur >= 0) select(cur);            // rifa' l'etichetta: freccia, parlanti, anteprima
}
$('dlgLabel').onclick   = () => apriTendina('dialogue', !dlgAperto);
$('descrLabel').onclick = () => apriTendina('description', !descrAperto);

$('prev').onclick = () => passa(-1);
$('next').onclick = () => passa(+1);
$('fprev').onclick = () => goToFrame(frameNow() - 1);
$('fnext').onclick = () => goToFrame(frameNow() + 1);
$('split').onclick = () => splitShotAt(frameNow());
$('mergeprev').onclick = () => mergeShotWithPrev(cur);
// Correggere 307 confini col mouse si sente nei polsi. Le lettere stanno sui bottoni (`title`),
// se no una scorciatoia che nessuno conosce e' codice morto.
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); annulla(); return; }
  if (e.metaKey || e.ctrlKey || e.altKey) return;      // il resto resta del browser
  const p = $('player');
  if (e.key === 'Escape' && daFondere !== null) { daFondere = null; avvisoFusione(); renderCast(); return; }
  if (e.key === 'r') { mostraVista('coda'); return; }
  if (e.key === 't') { mostraVista('scheda'); return; }
  if (e.key === 'h') { mostraVista('aiuto'); return; }
  if (e.key === 'v' && revisione()) { segnaVisto(); return; }
  if (e.key === 'd') { apriTendina('dialogue', !dlgAperto); return; }
  if (e.key === 'e') { apriTendina('description', !descrAperto); return; }
  // in revisione le frecce scorrono la coda, non gli shot: e' quello che stai smaltendo
  if (e.key === 'ArrowDown' || e.key === 'j') revisione() ? vaiInCoda(+1) : passa(+1);
  if (e.key === 'ArrowUp'   || e.key === 'k') revisione() ? vaiInCoda(-1) : passa(-1);
  if (e.key === 'ArrowLeft')  { e.preventDefault(); goToFrame(frameNow() - 1); }
  if (e.key === 'ArrowRight') { e.preventDefault(); goToFrame(frameNow() + 1); }
  // lo spazio parte da un tasto premuto dall'utente, quindi il `play()` non viene bloccato
  if (e.key === ' ') { e.preventDefault(); p.paused ? p.play().catch(() => {}) : p.pause(); }
  if (e.key === 's' && !$('split').disabled)      splitShotAt(frameNow());
  if (e.key === 'm' && !$('mergeprev').disabled)  mergeShotWithPrev(cur);
});
const cercato = () => { renderFiltri(); renderList($('filter').value.toLowerCase()); };
$('filter').addEventListener('input', cercato);
// la descrizione non compare nella riga, quindi qui il testo trovato non si evidenzia: filtra e
// basta, ed e' il modo piu' veloce di arrivare a «quello shot con la macchina che entra in campo»
$('filterDescr').addEventListener('input', cercato);

function scarica(testo, estensione, tipo) {
  const blob = new Blob([testo], {type: tipo});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = (DATA.video || 'catalog').replace(/\\.[^.]+$/, '') + estensione;
  a.click();
  URL.revokeObjectURL(a.href);
  $('saved').textContent = 'esportato ✓';
}
$('export').onclick = () => scarica(JSON.stringify(DATA, null, 2), '_catalog.json', 'application/json');
$('menuExport').addEventListener('click', e => {
  if (e.target.closest('.voci')) $('menuExport').open = false;
});
document.addEventListener('click', e => {
  if (!e.target.closest('#menuExport')) $('menuExport').open = false;
});

// --------------------------------------------------------------- esporta ---
// I confini stanno gia' al fotogramma: farne una lista di montaggio e' cambiare notazione, non
// convertire. `fps` non intero (23,976) si arrotonda per il **timecode**, che conta fotogrammi
// interi — e' la convenzione di CMX3600, e il non-drop frame e' quello giusto per un film intero.
const due = n => String(n).padStart(2, '0');
function tc(frame) {
  const f = Math.round(DATA.fps), t = Math.floor(frame / f);
  return `${due(Math.floor(t/3600))}:${due(Math.floor(t/60)%60)}:${due(t%60)}:${due(frame % f)}`;
}

function edl() {
  const nome = (DATA.video || 'catalogo').replace(/\\.[^.]+$/, '');
  const righe = [`TITLE: ${nome}`, 'FCM: NON-DROP FRAME', ''];
  shots.forEach((sh, i) => {
    // `end_frame` e' inclusivo, l'EDL vuole l'estremo **escluso**: +1, come ovunque nel progetto
    const a = tc(sh.start_frame), b = tc(sh.end_frame + 1);
    righe.push(`${String(i+1).padStart(3,'0')}  AX       V     C        ${a} ${b} ${a} ${b}`);
    righe.push(`* FROM CLIP NAME: ${DATA.video || nome}`);
    const testo = [sh.dialogue, sh.description].filter(Boolean).join(' — ');
    if (testo) righe.push('* COMMENT: ' + testo.replace(/\\s+/g, ' ').slice(0, 200));
    righe.push('');
  });
  return righe.join('\\n');
}
$('edl').onclick = () => scarica(edl(), '.edl', 'text/plain');

function srt() {
  const t = s => {
    const ms = Math.round(s * 1000);
    return `${due(Math.floor(ms/3600000))}:${due(Math.floor(ms/60000)%60)}:`
         + `${due(Math.floor(ms/1000)%60)},${String(ms%1000).padStart(3,'0')}`;
  };
  let n = 0;
  return shots.filter(sh => sh.dialogue)
    .map(sh => `${++n}\\n${t(sh.start_time)} --> ${t(sh.end_time)}\\n${sh.dialogue.trim()}\\n`)
    .join('\\n');
}
$('srt').onclick = () => scarica(srt(), '.srt', 'text/plain');

// Il raggruppamento dei volti sbaglia in un verso solo che si possa correggere a mano: **spezza**
// una persona in due gruppi (illuminazione, profilo, cappello). Unirli e' un lavoro da occhio
// umano, e qui costa due clic: il primo sceglie chi sparisce, il secondo in chi confluisce.
let daFondere = null;

function avvisoFusione() {
  const a = $('fondiAvviso');
  a.hidden = daFondere === null;
  if (daFondere !== null)
    a.textContent = `unisci «${(castById[daFondere] || {}).name || daFondere}» in… `
                  + `scegli un altro personaggio, o Esc per lasciar perdere`;
}

function fondiPersonaggi(da, verso) {
  if (da === verso) return;
  ricorda();
  shots.forEach(sh => {
    if (!sh.characters || !sh.characters.includes(da)) return;
    sh.characters = [...new Set(sh.characters.map(x => x === da ? verso : x))];
  });
  const i = cast.findIndex(c => c.id === da);
  if (i >= 0) cast.splice(i, 1);
  delete castById[da];
  // il conteggio va rifatto sui dati, non sommato: uno shot dove c'erano tutti e due contava due
  // volte e il numero saliva senza che nessuno shot fosse cambiato
  const target = castById[verso];
  if (target) target.n_shots = shots.filter(sh => (sh.characters || []).includes(verso)).length;
  if (charFilter === da) charFilter = verso;
  daFondere = null;
  avvisoFusione();
  dirty();
  renderCast();
  renderList($('filter').value.toLowerCase());
  if (cur >= 0) renderChips(shots[cur]);
}

function renderCast() {
  const el = $('cast'); el.innerHTML = '';
  cast.forEach(c => {
    const card = document.createElement('div');
    card.className = 'castcard' + (charFilter === c.id ? ' active' : '') + (c.uncertain ? ' unc' : '');
    const face = c.thumb ? `<img src="${encodeURI(c.thumb)}" alt="">`
                         : `<div class="ph">${esc((c.name||'?').slice(0,1))}</div>`;
    // `uncertain`: il rilevatore non lo dà per volto umano (droidi, elmetti). Cluster cosi'
    // fondono personaggi diversi, quindi il nome non vale — ed e' escluso dal prompt del VLM.
    card.innerHTML = face + `<input value="${esc(c.name)}" title="rinomina personaggio">`
                          + `<span class="n" title="${c.uncertain ? 'volto non riconosciuto come umano: questo gruppo puo\\' contenere personaggi diversi, ed e\\' escluso dalle descrizioni' : ''}">`
                          + `${c.uncertain ? '⚠ ' : ''}${c.n_shots} shot</span>`;
    const fondi = document.createElement('button');
    fondi.className = 'fondi';
    fondi.textContent = '⇄';
    fondi.title = 'unisci questo personaggio in un altro';
    fondi.onclick = e => {
      e.stopPropagation();
      daFondere = daFondere === c.id ? null : c.id;
      avvisoFusione();
      renderCast();
    };
    card.appendChild(fondi);
    if (daFondere === c.id) card.classList.add('dafondere');
    else if (daFondere !== null) card.classList.add('bersaglio');
    const input = card.querySelector('input');
    input.addEventListener('click', e => e.stopPropagation());
    input.addEventListener('input', e => { c.name = e.target.value; dirty(); if (cur>=0) renderChips(shots[cur]); });
    card.addEventListener('click', () => {
      // con una fusione in corso il clic sceglie il bersaglio, non il filtro
      if (daFondere !== null && daFondere !== c.id) return fondiPersonaggi(daFondere, c.id);
      charFilter = (charFilter === c.id ? null : c.id);
      renderCast(); renderList($('filter').value.toLowerCase());
    });
    el.appendChild(card);
  });
}

function renderChips(sh) {
  const el = $('chips'); el.innerHTML = '';
  (sh.characters || []).forEach(id => {
    const c = castById[id]; if (!c) return;
    const chip = document.createElement('span');
    chip.className = 'chip';
    chip.textContent = c.name;
    chip.title = 'filtra per ' + c.name;
    chip.onclick = () => { charFilter = id; renderCast(); renderList($('filter').value.toLowerCase()); };
    el.appendChild(chip);
  });
}

const ripescate = ripescaLocale();
renderFiltri();
renderMeta();
checkScenes();
renderList();
renderTimeline();
renderCast();
select(0);
$('annulla').onclick = annulla;
coda = daRivedere();
$('rivedi').title = `${coda.length} confini incerti o graduali, dal piu' incerto (R)`;
$('rivedi').onclick = () => mostraVista('coda');
$('scheda').onclick = () => mostraVista('scheda');
$('aiuto').onclick = () => mostraVista('aiuto');
if (ripescate) {
  // Ripescare e' gia' una modifica: va detto, e va potuta buttare via. Restare dentro un
  // ripescaggio sbagliato senza via d'uscita e' peggio che non aver ripescato niente.
  $('saved').textContent = '● ripescate dal browser, non esportate ';
  const b = document.createElement('button');
  b.textContent = 'scarta';
  b.title = 'butta la copia nel browser e ricarica il catalogo come sta su disco';
  b.onclick = () => { try { localStorage.removeItem(CHIAVE); } catch (e) {} location.reload(); };
  $('saved').appendChild(b);
}
</script>
</body>
</html>
"""


def build_html(manifest, title=None):
    """Genera la UI HTML self-contained del catalogo dal manifest."""
    data = json.dumps(manifest, ensure_ascii=False).replace("</", "<\\/")
    title = title or manifest.get("video") or "Catalogo scene"
    return (_TEMPLATE.replace("__FONT__", _font_face())
                     .replace("__DATA__", data)
                     .replace("__TITLE__", html.escape(title)))
