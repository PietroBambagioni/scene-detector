"""La timeline come pagina condivisibile: stesse cose di `timeline.py`, ma autonoma.

Le miniature diventano data URI dentro l'HTML — la pagina pubblicata non può chiedere file
al disco di nessuno. Sono ~2,8 MB di base64, contro il tetto di 16 MB.

    .venv/bin/python fuoricampo/artifact.py
"""
from __future__ import annotations

import base64
import html as _html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from impronta import PARTI
from timeline import (GIRATO, MANIFEST, QUI, con_controllo, copertura, durate_girato,
                      etichetta, hms, per_shot)
ETICHETTA_TIPO = {"scena": "scena vera, non ritrovata",
                  "cartello": "cartello o didascalia — fatto in montaggio",
                  "nero": "fotogrammi neri"}

# Le tre famiglie sono tutte a licenza SIL Open Font License, quindi si possono incorporare
# nel file e ridistribuire. Vedi la sezione «Licenze» in CLAUDE.md.
FONT_CSS = ("https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;800"
            "&family=IBM+Plex+Mono:wght@400;500"
            "&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&display=swap")
AGENTE = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


MESI = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
        "settembre", "ottobre", "novembre", "dicembre")


def _giorno(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return f"{d.day} {MESI[d.month - 1]} {d.year}"


def provenienza() -> str:
    """Da che run viene questo file: data, soglie, parti, la catena dei passi.

    Una pagina autonoma gira per posta e sopravvive al codice che l'ha fatta — in due giorni
    qui è cambiato il numero di parti del girato. Senza questa riga, chi la riceve non ha
    modo di sapere se sta guardando il run di prima o quello di dopo, e due file identici
    nell'aspetto raccontano numeri diversi. I dati vengono da `run.json`, scritto dai passi
    mentre girano (`annota_passo`), non letto dal sorgente adesso.
    """
    f = QUI / "run.json"
    if not f.exists():
        return ""
    r = json.loads(f.read_text())
    s, passi = r.get("soglie", {}), r.get("passi", [])
    quando = next((p["quando"] for p in reversed(passi) if "quando" in p), None)
    parti = r.get("parti") or []
    catena = " → ".join(f'{p["passo"]} {p["n"]}' for p in passi)
    fine = passi[-1] if passi else {}
    num = lambda x, d=1: f"{x:.{d}f}".replace(".", ",")
    return (
        '<p class="prov">'
        + (f"Dati dal run del <b>{_giorno(quando)}</b>. " if quando else "")
        + (f"Impronta a {num(s['TH_FRAME'], 2)}/{num(s['TH_SEG'], 2)} per almeno "
           f"{s['MIN_LEN']} campioni" if s else "")
        + (f", su {len(parti)} parti del girato (FC{parti[0]}–FC{parti[-1]})." if parti else ".")
        + (f" Passi: {catena} segmenti, {num(fine['copertura_min'])} min di film."
           if catena else "")
        + f" Pagina generata il {_giorno(datetime.now().astimezone().isoformat())}.</p>")


def stile_comune() -> str:
    """Il CSS che le pagine del sottoprogetto hanno in comune: token, tipografia, barre, chip.

    Sta qui e non copiato in ogni pagina perché il colore **è** l'informazione — la famiglia
    fredda per il girato, quella calda per il mancante — e due copie della tavolozza divergono
    alla prima ritaratura. Le regole specifiche di una pagina le aggiunge la pagina, dopo.
    """
    return """:root {
  --fondo:#F4F5F3; --carta:#FFFFFF; --inchiostro:#14161A; --tenue:#5C6169;
  --linea:#DEE0DC; --linea-forte:#C9CCC7; --pista:#E7E9E5;
  /* Due famiglie che non si toccano: il girato ritrovato sta nei **freddi**, quello che
     manca nei **caldi**. Prima il rosso delle scene mancanti era anche il colore di FC5 e i
     cartelli erano grigi sul grigio: due sistemi diversi che si contendevano la stessa tinta. */
  /* I quattro colori originali che non sono né gialli né rossi — ciano, verde, magenta, blu —
     più due che riempiono i posti lasciati dall'ocra e dal rosso, tenendosi lontani dai caldi
     riservati al mancante. */
  --p1:#1F8F7A; --p2:#2E8C9E; --p3:#4A8B3C; --p4:#A34A86; --p5:#6C5CD4; --p6:#4A5FA8;
  --manca-scena:#C62828; --manca-cartello:#B85C00; --manca-nero:#8A6D00;
  --display:"Archivo","Helvetica Neue",Arial,sans-serif;
  --corpo:"Newsreader",Georgia,"Times New Roman",serif;
  --mono:"IBM Plex Mono",ui-monospace,"SF Mono",Menlo,monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --fondo:#0E1013; --carta:#171A1E; --inchiostro:#E8E9E6; --tenue:#959BA4;
    --linea:#252930; --linea-forte:#39404A; --pista:#1D2126;
    --p1:#45C0A6; --p2:#4FB3C6; --p3:#6DB25C; --p4:#C878AC; --p5:#9788EE; --p6:#7B8FD4;
    --manca-scena:#FF5A4E; --manca-cartello:#FFA03D; --manca-nero:#F0CB3A;
  }
}
:root[data-theme="dark"] {
  --fondo:#0E1013; --carta:#171A1E; --inchiostro:#E8E9E6; --tenue:#959BA4;
  --linea:#252930; --linea-forte:#39404A; --pista:#1D2126;
  --p1:#45C0A6; --p2:#4FB3C6; --p3:#6DB25C; --p4:#C878AC; --p5:#9788EE; --p6:#7B8FD4;
  --manca-scena:#FF5A4E; --manca-cartello:#FFA03D; --manca-nero:#F0CB3A;
}
* { box-sizing:border-box; }
body { margin:0; background:var(--fondo); color:var(--inchiostro);
  font-family:var(--corpo); font-size:17px; line-height:1.6;
  -webkit-font-smoothing:antialiased; }
html { background:var(--fondo); }
.foglio { max-width:1120px; margin:0 auto; padding:clamp(1.5rem,4vw,4rem) clamp(1rem,4vw,2.5rem) 6rem; }

header.testata { border-bottom:2px solid var(--inchiostro); padding-bottom:1.6rem; }
.occhiello { font-family:var(--mono); font-size:.7rem; letter-spacing:.16em;
  text-transform:uppercase; color:var(--tenue); }
h1 { font-family:var(--display); font-weight:800; font-size:clamp(2.4rem,7vw,4.2rem);
  line-height:.98; letter-spacing:-.025em; margin:.5rem 0 .6rem; text-wrap:balance; }
h1 em { font-style:italic; font-family:var(--corpo); font-weight:400; letter-spacing:-.01em; }
.sommario { max-width:62ch; color:var(--tenue); margin:0; }

.cifre { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:1px; background:var(--linea); border:1px solid var(--linea);
  margin:2.5rem 0 3.5rem; }
.cifra { background:var(--carta); padding:1.1rem 1.2rem; }
.cifra b { display:block; font-family:var(--mono); font-weight:500;
  font-size:1.9rem; letter-spacing:-.03em; font-variant-numeric:tabular-nums; }
.cifra span { font-family:var(--mono); font-size:.68rem; letter-spacing:.1em;
  text-transform:uppercase; color:var(--tenue); }

h2 { font-family:var(--display); font-weight:600; font-size:1.05rem; letter-spacing:.02em;
  margin:0 0 .3rem; }
.guida { color:var(--tenue); font-size:.92rem; margin:0 0 1.4rem; max-width:60ch; }

.riga { display:grid; grid-template-columns:11rem 1fr 2.6rem; align-items:center;
  gap:.9rem; margin-bottom:.32rem; }
.riga.film { margin-bottom:1.1rem; }
.et { display:flex; flex-direction:column; align-items:flex-end; line-height:1.25; }
.nome { font-family:var(--display); font-weight:600; font-size:.86rem; }
.pip { display:inline-block; width:.55rem; height:.55rem; margin-right:.4rem;
  vertical-align:baseline; }
.dur, .quota { font-family:var(--mono); font-size:.68rem; color:var(--tenue);
  font-variant-numeric:tabular-nums; }
.pista { position:relative; height:20px; background:var(--pista);
  border:1px solid var(--linea); }
.riga.film .pista { height:40px; border-color:var(--linea-forte); }
.scala { display:flex; justify-content:space-between; font-family:var(--mono);
  font-size:.66rem; color:var(--tenue); margin:.35rem 0 2.6rem;
  padding-left:11.9rem; padding-right:3.5rem; }

.filtri { display:flex; flex-wrap:wrap; gap:.4rem; align-items:center;
  margin:3.5rem 0 1.6rem; padding-top:1.6rem; border-top:1px solid var(--linea); }
.chip { font-family:var(--mono); font-size:.72rem; padding:.34rem .7rem;
  border:1px solid var(--linea-forte); background:transparent; color:var(--inchiostro);
  cursor:pointer; }
.chip[aria-pressed="true"] { background:var(--inchiostro); color:var(--fondo);
  border-color:var(--inchiostro); }

@media (max-width:760px) {
  .riga { grid-template-columns:5.5rem 1fr 2.4rem; gap:.5rem; }
  .scala { padding-left:6rem; padding-right:3rem; }
  .legenda { margin-left:6rem; }
}"""


def font_incorporati() -> str:
    """I @font-face con il woff2 dentro il file, così la pagina non chiede niente a nessuno.

    Solo il sottoinsieme `latin`: copre gli accenti italiani e sono ~150 KB invece di 1 MB.
    I file scaricati restano in `font/` e non si riscaricano.
    """
    cache = QUI / "font"
    cache.mkdir(exist_ok=True)
    css = cache / "google.css"
    if not css.exists():
        css.write_text(subprocess.run(
            ["curl", "-sfL", "-m", "30", "-A", AGENTE, FONT_CSS],
            capture_output=True, text=True, check=True).stdout)

    fuori = []
    for commento, blocco in re.findall(r"/\* (\w[\w-]*) \*/\s*(@font-face \{.*?\})",
                                       css.read_text(), re.S):
        if commento != "latin":
            continue
        url = re.search(r"url\((https://[^)]+\.woff2)\)", blocco).group(1)
        f = cache / url.rsplit("/", 1)[1]
        if not f.exists():
            subprocess.run(["curl", "-sfL", "-m", "30", "-o", str(f), url], check=True)
        dato = "data:font/woff2;base64," + base64.b64encode(f.read_bytes()).decode()
        fuori.append(re.sub(r"url\(https://[^)]+\.woff2\)", f"url({dato})", blocco))
    if not fuori:
        raise RuntimeError("nessun @font-face latin trovato: il CSS di Google è cambiato")
    return "<style>\n" + "\n".join(fuori) + "\n</style>"


def b64(p: Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()


def e(s) -> str:
    return _html.escape(str(s), quote=True)


def controlla_js(pagina: str) -> None:
    """`node --check` sullo script della pagina, se node c'è.

    La pagina ha un solo `<script>`: un errore di sintassi non rompe una funzione, le
    spegne tutte — filtri e timeline compresi, che con l'ultima cosa aggiunta non c'entrano
    niente. È già successo (graffe raddoppiate in una stringa che non era una f-string) e da
    fuori si vede solo «nessun bottone funziona», senza indizi su chi sia il colpevole.
    """
    if not shutil.which("node"):
        return
    js = re.search(r"<script>(.*?)</script>", pagina, re.S)
    if not js:
        return
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(js.group(1))
        percorso = f.name
    try:
        esito = subprocess.run(["node", "--check", percorso], capture_output=True, text=True)
        if esito.returncode != 0:
            raise SystemExit(f"JavaScript non valido, pagina non scritta:\n{esito.stderr}")
    finally:
        Path(percorso).unlink(missing_ok=True)


def classifica(shots) -> dict[int, str]:
    """Che cosa sono gli shot che il girato non contiene: nero, cartello o scena vera.

    La distinzione conta più di quanto sembri: cartelli e neri Grifi li ha **creati in
    montaggio**, quindi nel girato non possono esserci e non sono un limite del metodo. Le
    scene vere sì: quelle o stanno in una parte non trasmessa, o ci sono sfuggite.
    """
    import numpy as np
    from impronta import FPS, riduci, smonta_gradiente
    from match import contrasto_film, moto_film

    grezzo = np.load(QUI / "dati" / "Anna.npy")
    contr = contrasto_film(grezzo)
    moto = moto_film(smonta_gradiente(riduci(grezzo.astype(np.float32))))
    fuori = {}
    for sh in shots:
        i, j = int(sh["start_time"] * FPS), max(int(sh["end_time"] * FPS),
                                                int(sh["start_time"] * FPS) + 1)
        c, m = float(np.median(contr[i:j])), float(np.median(moto[i:j]))
        d = (sh.get("description") or "").lower()
        parole = any(k in d for k in ("testo", "didascalia", "scritta", "schermo nero",
                                      "fotogrammi neri", "cartello", "titol"))
        fuori[sh["index"]] = ("nero" if c < 10 else
                              "cartello" if parole or (c < 30 and m < 0.3) else "scena")
    return fuori


def immagine(f: Path, modo: str) -> str:
    """base64 dove la pagina deve bastare a se stessa, path relativo dove no.

    La pagina di lavoro si rigenera in continuazione: 2,2 MB di base64 a ogni ricarica sono
    tempo buttato, e i fotogrammi stanno comunque nella cartella accanto.
    """
    return f"../thumbs/{f.name}" if modo == "lavoro" else b64(f)


def buchi_per_tipo(righe, segs, durata_film) -> list[tuple[float, float, str, int]]:
    """Gli intervalli di film che nessun segmento copre, ognuno col tipo dello shot in cui cade.

    Serve a rendere leggibile l'assenza: senza, il non ritrovato è solo spazio vuoto sulla
    barra, e non si distingue un buco di cartelli — che nel girato non possono esserci — da un
    buco di scene vere, che è l'unico che vale la pena inseguire.
    """
    coperti = sorted((s["film_start"], s["film_end"]) for s in segs)
    vuoti, t = [], 0.0
    for a, b in coperti:
        if a - t > 0.4:
            vuoti.append((t, a))
        t = max(t, b)
    if durata_film - t > 0.4:
        vuoti.append((t, durata_film))

    fuori = []
    for a, b in vuoti:
        for sh, _, _ in righe:                       # spezza il vuoto sui confini degli shot
            x, y = max(a, sh["start_time"]), min(b, sh["end_time"])
            if y - x > 0.4:
                fuori.append((x, y, sh.get("classe", "scena"), sh["index"]))
    return fuori


def costruisci(righe, segs, durata_film, durate, modo: str = "artifact") -> str:
    # Il banco dei filmati e le correzioni valgono per **ogni** pagina che gira da `file://`:
    # il download dell'export è inerte solo dentro un artifact pubblicato sul web. Chi riceve
    # il file autonomo può quindi annotare, esportare e rimandare il JSON — e guardare i
    # filmati, se ce li ha in una cartella `ANNA/` accanto al file.
    autonoma = modo in ("offline", "lavoro")
    # a ogni segmento lo shot che copre di più: cliccando una barra si arriva alla scheda
    shot_di = {}
    for sh, trovati, _ in righe:
        for k, sg in enumerate(segs):
            ov = min(sh["end_time"], sg["film_end"]) - max(sh["start_time"], sg["film_start"])
            if ov > shot_di.get(k, (0, None))[0]:
                shot_di[k] = (ov, sh["index"])

    def barra(dati, durata, chiave0, chiave1, parte_di):
        out = []
        for k, s in dati:
            x = s[chiave0] / durata * 100
            w = max((s[chiave1] - s[chiave0]) / durata * 100, 0.09)
            sh = shot_di.get(k, (0, None))[1]
            out.append(
                f'<button class="sg" style="left:{x:.4f}%;width:{w:.4f}%;'
                f'--c:var(--p{parte_di(s)})" data-k="{k}"'
                + (f' data-shot="{sh:03d}"' if sh is not None else "")
                + f' title="{hms(s[chiave0])}–{hms(s[chiave1])} · correlazione {s["score"]}"'
                f' aria-label="segmento {hms(s[chiave0])}"></button>')
        return "".join(out)

    film_bar = barra(list(enumerate(segs)), durata_film, "film_start", "film_end",
                     lambda s: s["parte"])
    righe_girato = []
    for p in PARTI:
        dati = [(k, s) for k, s in enumerate(segs) if s["parte"] == p]
        usati = copertura((s["girato_start"], s["girato_end"]) for _, s in dati)
        righe_girato.append(
            f'<div class="riga"><div class="et"><span class="nome">'
            f'<i class="pip" style="background:var(--p{p})"></i>{etichetta(p)}</span>'
            f'<span class="dur">{hms(durate[p])}</span></div>'
            f'<div class="pista">{barra(dati, durate[p], "girato_start", "girato_end", lambda s: p)}</div>'
            f'<span class="quota">{usati/durate[p]:.0%}</span></div>')

    trovati = [(sh, t, c) for sh, t, c in righe if t]
    mancanti = [sh for sh, t, _ in righe if not t]

    schede = []
    for sh, tr, cop in trovati:
        t = tr[0]
        i = sh["index"]
        f_img, g_img = QUI / "thumbs" / f"f{i:03d}.jpg", QUI / "thumbs" / f"g{i:03d}.jpg"
        # gli stessi due istanti delle miniature: il video parte dove il fotogramma mostra
        t_film = (t["film_da"] + t["film_a"]) / 2
        t_gir = (t["girato_start"] + t["girato_end"]) / 2
        confronta = (
            f'<button class="confronta" data-p="{t["parte"]}" data-tf="{t_film:.2f}" '
            f'data-tg="{t_gir:.2f}" data-fine="{t["film_a"]:.2f}" '
            f'data-shot="{i:03d}">▶ confronta</button>'
        ) if autonoma else ""
        ctrl = t.get("controllo")
        # 0,648 è il massimo raggiunto da quaranta accoppiamenti casuali: sotto quel valore
        # il segmento non si distingue dal caso, e va guardato prima di crederci
        dubbio = ctrl is not None and ctrl <= 0.648
        verifica = (f' · <b class="ctrl{" giu" if dubbio else ""}">verifica {ctrl:.2f}</b>'
                    if ctrl is not None else "")
        # Il tempo accanto al nome è la durata dello **shot**; quello sotto le miniature è
        # l'istante del **fotogramma**, che sta al centro della sola porzione ritrovata. Finché
        # la copertura è piena i due quasi coincidono, ma su uno shot ritrovato a metà
        # divergono di minuti e sembrano in contraddizione. Il pezzo che mancava è il terzo:
        # *quale* parte dello shot è stata ritrovata.
        parziale = (t["film_da"] - sh["start_time"] > 2.0
                    or sh["end_time"] - t["film_a"] > 2.0)
        accoppiato = (
            f'<p class="accoppiato">il fotogramma viene dal pezzo '
            f'<b>{hms(t["film_da"])}–{hms(t["film_a"])}</b>, accoppiato a {etichetta(t["parte"], True)} '
            f'{hms(t["girato_start"])}–{hms(t["girato_end"])}'
            + (f' · lo shot è coperto da {len(tr)} pezzi' if len(tr) > 1 else '')
            + '</p>') if parziale else ""
        verdetti = ("".join(
            f'<button class="vd" data-v="{v}" title="{titolo}">{segno}</button>'
            for v, segno, titolo in (("giusto", "✓", "aggancio giusto"),
                                         ("sbagliato", "✗", "aggancio sbagliato"),
                                         ("incerto", "?", "non si capisce")))
        ) if autonoma else ""
        schede.append(f"""<article class="scheda" id="shot-{i:03d}" data-parte="{t['parte']}"
 data-sf="{sh['start_frame']}" data-shot="{i:03d}" data-ctrl="{ctrl if ctrl is not None else 1}"
 data-testo="{e((sh.get('description') or '').lower())}"
 data-parlato="{e((sh.get('dialogue') or '').lower())}">
 <div class="visivo">
  <figure><img src="{immagine(f_img, modo)}" alt="fotogramma dal film" loading="lazy">
   <figcaption>fotogramma a <b>{hms(t_film)}</b></figcaption></figure>
  <figure><img src="{immagine(g_img, modo)}" alt="fotogramma dal girato" loading="lazy">
   <figcaption style="--c:var(--p{t['parte']})">{etichetta(t['parte'], True)}, a <b>{hms(t_gir)}</b></figcaption></figure>
 </div>
 <div class="testo">
  <header><span class="num">Shot {i:03d}</span>
   <span class="tc" title="istante del fotogramma mostrato e fine dello shot nel montaggio">{hms(t_film)} → {hms(sh['end_time'])}</span>
   {confronta}
   <span class="misure">coperto {cop:.0%} · corr {t['score']:.2f}{verifica}</span></header>
  {accoppiato}
  <p class="descr">{e(sh.get('description') or '')}</p>
  <details class="parlato">
   <summary>{'trascrizione · ' + str(len((sh.get('dialogue') or '').split())) + ' parole'
             if sh.get('dialogue') else 'nessuna trascrizione'}</summary>
   <p class="dial">{('« ' + e(sh["dialogue"]) + ' »') if sh.get('dialogue') else ''}</p>
  </details>
  <div class="verdetti">{verdetti}</div>
 </div></article>""")

    banco = """
<section class="banco" id="banco" aria-label="confronto dei due filmati">
 <div class="schermi">
  <figure><video id="vf" preload="metadata" playsinline></video><figcaption>film</figcaption></figure>
  <figure><video id="vg" preload="metadata" playsinline muted></video><figcaption id="etg">girato</figcaption></figure>
 </div>
 <p id="guaio" hidden></p>
 <p id="fine" hidden></p>
 <div class="comandi">
  <button id="via" class="acceso" title="spazio">▶ parti insieme</button>
  <button id="indietro" title="−5 s su entrambi">−5s</button>
  <button id="avanti" title="+5 s su entrambi">+5s</button>
  <span class="sep">│</span>
  <span>audio</span>
  <button class="audio acceso" data-a="film">film</button>
  <button class="audio" data-a="girato">girato</button>
  <button class="audio" data-a="muto">muto</button>
  <span class="sep">│</span>
  <label>scarto <input type="range" id="reg" min="-3" max="3" step="0.1" value="0"></label>
  <span id="regv">0,0 s</span>
  <span class="sep">│</span>
  <select id="vel" aria-label="velocità">
   <option value="0.5">0,5×</option><option value="1" selected>1×</option>
   <option value="2">2×</option></select>
  <span class="sep">│</span>
  <span id="dove">—</span>
  <span id="scarto"></span>
  <button id="chiudi" title="chiudi il banco">✕</button>
 </div>
</section>""" if autonoma else ""

    barra_corr = """
<div class="barra-corr">
 <button id="correggi">✎ Correggi</button>
 <button id="esporta">↓ Esporta correzioni</button>
 <span id="conta">nessuna modifica</span>
</div>""" if autonoma else ""

    # Il JS del banco e delle correzioni: solo la pagina di lavoro lo porta. Le graffe sono
    # raddoppiate perché tutto il documento esce da una f-string.
    lavoro_js = """
const vf = document.getElementById('vf'), vg = document.getElementById('vg');
const banco = document.getElementById('banco');
let offset = 0, regolazione = 0, parteCorrente = null, schedaSuona = null;

// Il browser non sa elencare una cartella: una pagina aperta col doppio clic puo' solo chiedere
// un file e vedere se risponde. Quindi «una cartella qualsiasi» non esiste — esiste un elenco
// corto di posti provati in ordine. Primo della lista: accanto all'html, senza cartella.
// Nessun costo all'avvio: si scopre al primo confronto, sbagliando, e da li' in poi resta.
const POSTI = ['', 'ANNA/', 'video/'];
let posto = 0;
const percorso = nome => POSTI[posto] + encodeURIComponent(nome);
const parteGirato = p => percorso('Fuori campo di Anna - ' + p + '.mp4');
// Dove sono i filmati: si prova, e vince il **primo posto che risponde**. Il segnale e' sempre
// positivo — «questo file c'e'» — e mai l'assenza di uno: un <video> puntato su un file che non
// esiste, servito via http, non emette `error` affatto, fa `stalled` e resta in attesa (misurato,
// 15 s senza un evento utile). Da server la domanda si fa con `fetch`, che risponde subito e
// senza equivoci; da `file://` — il doppio clic, cioe' l'uso normale — `fetch` e' vietato e
// allora si prova a caricare davvero, aspettando i metadati.
function cePosto(dir) {
  const url = dir + encodeURIComponent('Anna.mp4');
  return fetch(url, {method: 'HEAD'}).then(r => r.ok).catch(() => new Promise(ok => {
    const v = document.createElement('video');
    v.preload = 'metadata';
    v.onloadedmetadata = () => ok(true);
    v.onerror = () => ok(false);
    setTimeout(() => ok(false), 4000);   // rete lenta o disco lento: si passa oltre e si riprova
    v.src = url;                         // al posto dopo, invece di restare fermi per sempre
  }));
}
const cercaPosto = (async () => {
  for (let i = 0; i < POSTI.length; i++)
    if (await cePosto(POSTI[i])) { posto = i; return; }
})();
let fineShot = null;      // dove finisce il pezzo accoppiato, nel tempo del film

function mostraDove() {
  const t = vf.currentTime;
  document.getElementById('dove').textContent =
    'film ' + fmt(t) + '  ·  girato ' + fmt(t + offset);
}
function fmt(s) {
  s = Math.max(0, s);
  const h = Math.floor(s/3600), m = Math.floor(s%3600/60), q = Math.floor(s%60);
  return h + ':' + String(m).padStart(2,'0') + ':' + String(q).padStart(2,'0');
}
function allinea() { vg.currentTime = Math.max(0, vf.currentTime + offset); }

function pronto(v, fn, aspetta) {
  // `readyState` dopo un cambio di src può ancora descrivere il file **precedente**: chi ha
  // appena cambiato sorgente deve aspettare `loadedmetadata` comunque, altrimenti si imposta
  // currentTime su un video non caricato e il tempo torna a zero appena arriva quello nuovo.
  if (!aspetta && v.readyState >= 1) fn();
  else v.addEventListener('loadedmetadata', fn, {once: true});
}
async function confronta(b) {
  const p = b.dataset.p;
  await cercaPosto;                     // di norma e' gia' finita: un clic umano arriva dopo
  const primoFilm = !vf.src;
  if (primoFilm) vf.src = percorso('Anna.mp4');
  const cambiaParte = parteCorrente !== p;
  if (cambiaParte) {                    // ricarica il girato solo se cambia la parte
    // Il nome vero del file, non un alias: chi riceve la pagina non deve rinominare niente.
    // `encodeURIComponent` per gli spazi — un src con gli spazi grezzi lo salva il parser
    // dell'URL, ma solo per caso, e qui il nome arriva da fuori.
    vg.src = parteGirato(p);
    parteCorrente = p;
    document.getElementById('etg').textContent = 'Fuori campo ' + p;
  }
  offset = (+b.dataset.tg) - (+b.dataset.tf) + regolazione;
  fineShot = +b.dataset.fine;
  document.getElementById('fine').hidden = true;
  banco.classList.add('aperto');
  if (schedaSuona) schedaSuona.classList.remove('suona');
  schedaSuona = b.closest('.scheda');
  schedaSuona.classList.add('suona');

  // Il film è un file da 8 GB con l'indice in fondo: la prima apertura può metterci qualche
  // secondo, e una pagina muta in quei secondi sembra rotta. Meglio dirlo, e dirlo anche se
  // l'attesa diventa troppo lunga.
  const dove = document.getElementById('dove');
  dove.textContent = 'carico…';
  clearTimeout(confronta.attesa);
  confronta.attesa = setTimeout(() => {
    if (vf.paused) {
      const g = document.getElementById('guaio');
      g.hidden = false;
      g.textContent = 'I filmati non sono partiti entro 20 s. Se stai guardando la pagina '
        + 'da un server, aprila invece col doppio click: in locale il video si apre subito.';
    }
  }, 20000);

  // Il permesso a riprodurre con l'audio si ottiene **solo dentro lo stack del click**: un
  // play() chiamato più tardi, dentro il callback di `loadedmetadata`, non è più considerato
  // avviato dall'utente e il browser lo blocca in silenzio. È per questo che al primo
  // confronto non partiva niente e poi «parti insieme» funzionava. Quindi si chiede di
  // riprodurre subito, qui, e i tempi si sistemano quando i metadati arrivano.
  const chiesto = Promise.all([vf.play(), vg.play()].map(q => q && q.catch(e => e)));
  chiesto.then(esiti => {
    const negato = esiti.find(e => e instanceof Error && e.name === 'NotAllowedError');
    if (negato) {
      const g = document.getElementById('guaio');
      g.hidden = false;
      g.textContent = 'Il browser ha bloccato la riproduzione automatica: premi «parti '
        + 'insieme» per avviarli.';
    }
  });

  const parti = () => {
    clearTimeout(confronta.attesa);
    document.getElementById('guaio').hidden = true;
    allinea();
    if (vf.paused) { vf.play(); vg.play(); }
    mostraDove();
  };
  pronto(vf, () => {
    vf.currentTime = +b.dataset.tf;
    pronto(vg, parti, cambiaParte);
  }, primoFilm);
  banco.scrollIntoView({block:'nearest'});
}
document.querySelectorAll('.confronta').forEach(b => b.onclick = () => confronta(b));

// una tacca del non ritrovato porta al fotogramma corrispondente, in fondo: è l'unico modo di
// vedere *che cosa* manca in quel punto senza cercarlo a mano fra novantatré miniature
document.querySelectorAll('button.vt').forEach(b => b.onclick = () => {
  const f = document.getElementById('manca-' + b.dataset.shot);
  if (!f) return;
  document.querySelectorAll('figure.assente.viva').forEach(o => o.classList.remove('viva'));
  f.classList.add('viva');
  f.scrollIntoView({behavior: 'smooth', block: 'center'});
});

// I due decoder non avanzano allo stesso passo: senza riallineamento divergono in un minuto.
// Ma riallineare con un salto si **vede**: il girato va a scatti. Sotto mezzo secondo si
// corregge cambiando impercettibilmente la velocità del girato — recupera da solo in qualche
// secondo e l'immagine resta continua. Il salto resta solo per gli scarti grandi, dove
// nessuna correzione di velocità arriverebbe in tempo.
// Un salto costringe il decoder a ripartire dal keyframe: il girato perde terreno proprio
// per essere stato riallineato, sfora di nuovo, salta di nuovo. Misurato sul campo: 16 salti
// in 16 secondi, cioè scatti continui. La soglia del salto va quindi tenuta **alta** — un
// secondo di disallineamento si sopporta, un video a scatti no — e il recupero affidato alla
// velocità, con un margine abbastanza largo da riprendere davvero (±12% recupera mezzo
// secondo in quattro).
const SCARTO_SALTO = 2.0;
const SCARTO_OK = 0.05;
const CORREZIONE_MAX = 0.12;
const OGNI_MS = 500;         // il ciclo gira 60 volte al secondo, ma la velocità si tocca
                             // due volte al secondo: cambiarla a ogni fotogramma produce da
                             // sola gli artefatti che si volevano togliere
let salti = 0, correzioni = 0, ultimaCorrezione = 0;
function tick() {
  if (!vf.paused && vg.readyState >= 2 && !vg.seeking) {
    const atteso = vf.currentTime + offset, d = vg.currentTime - atteso;
    const el = document.getElementById('scarto');
    el.textContent = 'scarto ' + (d >= 0 ? '+' : '') + d.toFixed(2) + ' s'
      + (salti ? ' · ' + salti + ' salti' : '');
    el.classList.toggle('male', Math.abs(d) > SCARTO_SALTO);
    const adesso = performance.now();
    // se il girato sta ancora caricando non si tocca: un salto adesso lo manda in stallo
    if (vg.readyState < 3) {
      /* aspetta che abbia di che riprodurre */
    } else if (Math.abs(d) > SCARTO_SALTO) {
      vg.currentTime = Math.max(0, atteso);
      vg.playbackRate = vf.playbackRate;
      ultimaCorrezione = adesso;
      salti++;
    } else if (adesso - ultimaCorrezione < OGNI_MS) {
      /* si lascia lavorare la correzione in corso */
    } else if (Math.abs(d) > SCARTO_OK) {
      ultimaCorrezione = adesso;
      // un ritardo si recupera andando un po' più veloce, un anticipo un po' più piano:
      // ±4% è sotto la soglia percettiva sull'immagine
      const correzione = Math.max(-CORREZIONE_MAX, Math.min(CORREZIONE_MAX, -d * 0.5));
      vg.playbackRate = vf.playbackRate * (1 + correzione);
      correzioni++;
    } else if (vg.playbackRate !== vf.playbackRate) {
      vg.playbackRate = vf.playbackRate;
      ultimaCorrezione = adesso;
    }
    mostraDove();
    // alla fine del pezzo accoppiato ci si ferma: il confronto è finito lì, e lasciar
    // scorrere il film oltre serve solo a far perdere il segno
    if (fineShot !== null) {
      const f = document.getElementById('fine');
      if (vf.currentTime >= fineShot) {
        f.hidden = false;
        f.textContent = 'fine dello shot montato';
        if (!vf.paused) { vf.pause(); vg.pause(); }
      } else if (!f.hidden) {
        f.hidden = true;
      }
    }
  }
  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);

const via = document.getElementById('via');
function insieme() {
  if (vf.paused) { allinea(); vf.play(); vg.play(); } else { vf.pause(); vg.pause(); }
  via.textContent = vf.paused ? '▶ parti insieme' : '⏸ ferma';
}
via.onclick = insieme;
vf.onpause = vf.onplay = () => { via.textContent = vf.paused ? '▶ parti insieme' : '⏸ ferma'; };
document.getElementById('avanti').onclick = () => { vf.currentTime += 5; allinea(); };
document.getElementById('indietro').onclick = () => { vf.currentTime -= 5; allinea(); };
document.getElementById('chiudi').onclick = () => {
  vf.pause(); vg.pause(); banco.classList.remove('aperto');
  if (schedaSuona) schedaSuona.classList.remove('suona');
};
document.addEventListener('keydown', ev => {
  if (ev.code === 'Space' && banco.classList.contains('aperto') &&
      !/^(INPUT|SELECT)$/.test(ev.target.tagName) && !ev.target.isContentEditable) {
    ev.preventDefault(); insieme();
  }
});
// Il girato è registrato 6÷9 dB più piano del film (misurato: −33/−36 dB contro −27), cioè
// circa un terzo dell'ampiezza: passando da una traccia all'altra sembra che non abbia audio.
// L'elemento <video> non amplifica oltre il suo volume nominale, quindi serve un guadagno.
// Si costruisce al primo click — un AudioContext creato prima di un gesto dell'utente nasce
// sospeso — e se il browser non lo permette si prosegue senza, con l'audio di prima.
let guadagno = null;
function amplifica() {
  if (guadagno !== null) return guadagno;
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const g = ctx.createGain();
    g.gain.value = 3.0;
    ctx.createMediaElementSource(vg).connect(g).connect(ctx.destination);
    ctx.createMediaElementSource(vf).connect(ctx.destination);
    if (ctx.state === 'suspended') ctx.resume();
    guadagno = g;
  } catch (e) {
    guadagno = false;      // niente Web Audio: resta il volume nativo
  }
  return guadagno;
}
document.querySelectorAll('.audio').forEach(b => b.onclick = () => {
  document.querySelectorAll('.audio').forEach(o => o.classList.toggle('acceso', o === b));
  if (b.dataset.a === 'girato') amplifica();
  vf.muted = b.dataset.a !== 'film';
  vg.muted = b.dataset.a !== 'girato';
});
const reg = document.getElementById('reg');
reg.oninput = () => {
  offset += (+reg.value) - regolazione;
  regolazione = +reg.value;
  document.getElementById('regv').textContent =
    regolazione.toFixed(1).replace('.', ',') + ' s';
  allinea(); mostraDove();
};
document.getElementById('vel').onchange = ev => {
  vf.playbackRate = +ev.target.value;    // al girato ci pensa il riallineamento
};

// ── correzioni ───────────────────────────────────────────────────────────────
const modifiche = {};                    // per start_frame, mai per indice
const sporche = new Set();               // gli shot toccati dall'ultima esportazione
const CHIAVE = 'fuoricampo-correzioni';
function conta() {
  const n = Object.keys(modifiche).length;
  const el = document.getElementById('conta');
  // si contano gli **shot** toccati, non i campi: correggere testo e verdetto sullo stesso
  // shot è una modifica sola per chi guarda
  el.textContent = sporche.size ? sporche.size + (sporche.size === 1 ? ' da esportare' : ' da esportare')
                 : n ? 'tutto esportato (' + n + ')' : 'nessuna modifica';
  el.classList.toggle('vive', sporche.size > 0);
  try { localStorage.setItem(CHIAVE, JSON.stringify(modifiche)); } catch (e) {}
}
function segna(art, campo, valore) {
  const sf = art.dataset.sf;
  if (!modifiche[sf]) modifiche[sf] = {shot: +art.dataset.shot};
  modifiche[sf][campo] = valore;
  sporche.add(sf);
  conta();
}
document.getElementById('correggi').onclick = ev => {
  const on = document.body.classList.toggle('correzione');
  ev.target.classList.toggle('acceso', on);
  document.querySelectorAll('.descr, .dial').forEach(
    d => d.contentEditable = on ? 'true' : 'false');
  // le tendine si aprono tutte: correggere una trascrizione che resta chiusa vorrebbe dire
  // scrivere dentro qualcosa che non si vede. Chiudendo la modalità restano aperte solo
  // quelle che sono state toccate.
  document.querySelectorAll('.parlato').forEach(d => {
    d.open = on || !!d.querySelector('.dial.toccata');
  });
};
document.querySelectorAll('.descr').forEach(d => d.addEventListener('input', () => {
  d.classList.add('toccata');
  segna(d.closest('.scheda'), 'descrizione', d.textContent.trim());
}));
// la trascrizione è generata da un riconoscitore automatico e sbaglia spesso: correggerla
// vale quanto correggere la descrizione, e va nello stesso JSON
document.querySelectorAll('.dial').forEach(d => d.addEventListener('input', () => {
  d.classList.add('toccata');
  segna(d.closest('.scheda'), 'dialogo', d.textContent.trim().replace(/^\\u00ab\\s*|\\s*\\u00bb$/g, ''));
}));
document.querySelectorAll('.vd').forEach(b => b.onclick = () => {
  const art = b.closest('.scheda');
  art.querySelectorAll('.vd').forEach(o => o.classList.toggle('scelto', o === b));
  segna(art, 'verdetto', b.dataset.v);
});
document.getElementById('esporta').onclick = () => {
  const dati = {generato: new Date().toISOString(), segmenti: SEGMENTI,
    correzioni: Object.entries(modifiche).map(([sf, v]) =>
      Object.assign({start_frame: +sf}, v))};
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(dati, null, 1)],
    {type: 'application/json'}));
  a.download = 'correzioni.json';
  a.click();
  URL.revokeObjectURL(a.href);
  // il file le contiene tutte, quindi da qui niente è più «in sospeso»: senza azzerare,
  // la pagina continua ad avvisare alla chiusura anche dopo che hai salvato
  sporche.clear();
  conta();
};
addEventListener('beforeunload', ev => {
  if (sporche.size) { ev.preventDefault(); ev.returnValue = ''; }
});
// rete di sicurezza contro la chiusura per sbaglio: l'archivio resta il JSON esportato
try {
  const vecchie = JSON.parse(localStorage.getItem(CHIAVE) || '{}');
  if (Object.keys(vecchie).length) {
    Object.assign(modifiche, vecchie);
    for (const [sf, v] of Object.entries(vecchie)) {
      const art = document.querySelector('.scheda[data-sf="' + sf + '"]');
      if (!art) continue;
      if (v.descrizione) {
        const d = art.querySelector('.descr');
        d.textContent = v.descrizione; d.classList.add('toccata');
      }
      if (v.dialogo) {
        const d = art.querySelector('.dial');
        d.textContent = '« ' + v.dialogo + ' »'; d.classList.add('toccata');
        const t = d.closest('.parlato');
        if (t) t.open = true;
      }
      if (v.verdetto) art.querySelectorAll('.vd').forEach(
        o => o.classList.toggle('scelto', o.dataset.v === v.verdetto));
    }
    sporche.clear();  // ripescate dal browser, non sono modifiche nuove di questa sessione
    conta();
  }
} catch (e) {}
""".replace("SEGMENTI", str(len(segs))) if autonoma else ""

    vuoti = buchi_per_tipo(righe, segs, durata_film)
    minuti_tipo = {k: sum(b - a for a, b, t, _ in vuoti if t == k) / 60
                   for k in ("scena", "cartello", "nero")}
    barra_vuoti = "".join(
        f'<button class="vt" style="left:{a/durata_film*100:.4f}%;'
        f'width:{max((b-a)/durata_film*100, 0.06):.4f}%;background:var(--manca-{t})" '
        f'data-t="{t}" data-shot="{i:03d}" title="{hms(a)}–{hms(b)} · {ETICHETTA_TIPO[t]} · '
        f'shot {i:03d}" aria-label="buco {hms(a)}"></button>' for a, b, t, i in vuoti)

    tot = copertura((s["film_start"], s["film_end"]) for s in segs)
    girato = sum(durate.values())
    # 0,648 è il massimo dei quaranta accoppiamenti casuali (vedi `dubbio`, più sopra)
    verificati = sum(1 for s in segs if s.get("controllo", 0) > 0.648)
    istruzioni = ("<b>Per guardare i filmati affiancati</b>: metti accanto a questo file una "
                  "cartella <code>ANNA</code> (o <code>video</code>, o nessuna cartella: vanno bene anche lì accanto) con dentro <code>Anna.mp4</code> (il montaggio) "
                  "e <code>Fuori campo di Anna - 1.mp4</code>…<code>- 5.mp4</code> (le cinque "
                  "parti trasmesse che entrano nel confronto: la sesta è un rimontaggio delle "
                  "altre ed è esclusa). Senza, "
                  "restano i fotogrammi e i minutaggi. Le correzioni si esportano in un JSON "
                  "che si applica con <code>applica_correzioni.py</code>.<br><br>"
                  if autonoma else "")
    ETICHETTE = {"cartello": ("Cartelli e didascalie",
                             "Creati in montaggio: nel girato non possono esistere."),
                 "nero": ("Fotogrammi neri",
                          "Stacchi e passaggi a nero del montaggio."),
                 "scena": ("Scene vere non ritrovate",
                           "Queste il girato potrebbe contenerle: o stanno in una parte non "
                           "trasmessa, o ci sono sfuggite.")}
    blocchi = []
    for classe in ("scena", "cartello", "nero"):
        gruppo = [sh for sh in mancanti if sh.get("classe") == classe]
        if not gruppo:
            continue
        titolo, spiega = ETICHETTE[classe]
        durata = sum(sh["end_time"] - sh["start_time"] for sh in gruppo)
        celle = "".join(
            f'<figure class="assente" id="manca-{sh["index"]:03d}"><img src="{immagine(QUI / "thumbs" / f"f{sh["index"]:03d}.jpg", modo)}"'
            f' alt="" loading="lazy" title="{e((sh.get("description") or "")[:180])}">'
            f'<figcaption>{sh["index"]:03d} · {hms(sh["start_time"])} · '
            f'{sh["end_time"] - sh["start_time"]:.0f}s</figcaption></figure>'
            for sh in gruppo)
        blocchi.append(
            f'<div class="gruppo"><h3>{titolo} <small>{len(gruppo)} shot · '
            f'{durata/60:.1f} min</small></h3><p class="guida">{spiega}</p>'
            f'<div class="griglia">{celle}</div></div>')
    voci_mancanti = "".join(blocchi)

    testa = font_incorporati() if autonoma else (
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        f'<link rel="stylesheet" href="{FONT_CSS}">')
    apri = ('<!doctype html>\n<html lang="it">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            if autonoma else "")
    chiudi = "\n</body>\n</html>" if autonoma else ""
    return f"""{apri}<title>Anna nel Fuori campo</title>
{testa}
<style>
{stile_comune()}
.sg {{ position:absolute; top:0; bottom:0; padding:0; border:0; cursor:pointer;
  background:var(--c); appearance:none; }}
.sg:hover {{ filter:brightness(1.25); }}
.sg.viva, .sg:focus-visible {{ outline:2px solid var(--inchiostro); outline-offset:1px;
  z-index:3; }}
.riga.vuoti {{ margin-top:.5rem; }}
.riga.vuoti .pista {{ height:14px; }}
button.vt {{ position:absolute; top:0; bottom:0; border:0; padding:0; cursor:pointer;
  border-radius:1px; appearance:none; }}
button.vt:hover {{ filter:brightness(1.4); }}
button.vt:focus-visible {{ outline:2px solid var(--inchiostro); outline-offset:1px; z-index:3; }}
figure.assente.viva {{ outline:2px solid var(--inchiostro); outline-offset:3px; }}
.legenda {{ display:flex; flex-wrap:wrap; gap:1.1rem; margin:.5rem 0 0 11.9rem;
  font-family:var(--mono); font-size:.66rem; color:var(--tenue); }}
.legenda i {{ display:inline-block; width:.6rem; height:.6rem; margin-right:.35rem;
  flex:0 0 auto; }}
.legenda .leg {{ display:flex; align-items:center; font:inherit; color:inherit;
  background:transparent; border:1px solid transparent; padding:.1rem .35rem;
  margin:-.1rem -.35rem; cursor:pointer; appearance:none; }}
.legenda .leg:hover, .legenda .leg:focus-visible {{ color:var(--inchiostro); }}
.legenda .leg[aria-pressed="true"] {{ color:var(--inchiostro);
  border-color:var(--linea-forte); }}
/* `hidden` scritto a mano: su un elemento con un `display` esplicito la regola dell'UA
   perderebbe, ed è una delle trappole di layout già pagate una volta */
button.vt[hidden] {{ display:none; }}
/* I due campi stanno in un involucro così vanno a capo **insieme**. Nessun `margin-left:auto`:
   spingendoli a destra, appena la riga andava a capo restavano appesi da soli con un vuoto in
   mezzo. Allineati a sinistra come i chip, la seconda riga comincia dove comincia la prima. */
.ricerche {{ display:flex; flex-wrap:wrap; gap:.4rem; }}
.cerca {{ font-family:var(--mono); font-size:.78rem; padding:.36rem .6rem;
  border:1px solid var(--linea-forte); background:var(--carta); color:var(--inchiostro);
  min-width:min(15rem,45vw); }}
.cerca::placeholder {{ color:var(--tenue); }}

.scheda {{ display:grid; grid-template-columns:minmax(0,320px) 1fr; gap:1.6rem;
  padding:1.5rem 0; border-top:1px solid var(--linea); scroll-margin-top:1rem; }}
.scheda.spenta {{ display:none; }}
.scheda.viva {{ background:var(--carta); box-shadow:0 0 0 1.2rem var(--carta); }}
.visivo {{ display:grid; grid-template-columns:1fr 1fr; gap:.5rem; }}
.visivo figure {{ margin:0; }}
.visivo img {{ width:100%; display:block; background:var(--pista); }}
figcaption {{ font-family:var(--mono); font-size:.64rem; color:var(--tenue);
  padding-top:.35rem; letter-spacing:.02em; }}
figcaption b {{ color:var(--c,var(--inchiostro)); font-weight:500; }}
.scheda header {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:.7rem;
  margin-bottom:.5rem; }}
.num {{ font-family:var(--display); font-weight:800; font-size:1.05rem;
  letter-spacing:-.01em; }}
.tc {{ font-family:var(--mono); font-size:.75rem; color:var(--tenue);
  font-variant-numeric:tabular-nums; }}
.misure {{ font-family:var(--mono); font-size:.68rem; color:var(--tenue);
  margin-left:auto; }}
.ctrl {{ font-weight:500; color:var(--inchiostro); }}
.ctrl.giu {{ color:#fff; background:var(--p5); padding:.05rem .35rem; }}
.scheda p {{ margin:0; font-size:.98rem; max-width:66ch; }}
.dial {{ color:var(--tenue); font-style:italic; margin-top:.5rem !important; }}
.parlato {{ margin-top:.6rem; }}
.parlato summary {{ font-family:var(--mono); font-size:.68rem; color:var(--tenue);
  cursor:pointer; list-style:none; display:flex; align-items:center; gap:.35rem;
  padding:.15rem 0; width:fit-content; }}
.parlato summary::-webkit-details-marker {{ display:none; }}
.parlato summary::before {{ content:"▸"; font-size:.8rem; transition:transform .15s; }}
.parlato[open] summary::before {{ transform:rotate(90deg); }}
.parlato summary:hover {{ color:var(--inchiostro); }}
@media (prefers-reduced-motion:reduce) {{ .parlato summary::before {{ transition:none; }} }}
/* La matita sta sopra il banco (`z-index:20`) perché deve restare raggiungibile anche
   mentre i due filmati sono aperti. Fuori dal `.foglio`: se fosse dentro, la modalità di
   scrittura renderebbe modificabile anche il bottone che la spegne. */
.penna {{ position:fixed; top:.7rem; right:.7rem; z-index:40; display:flex; gap:.3rem; }}
.penna button {{ font-family:var(--mono); font-size:.82rem; line-height:1;
  padding:.5rem .62rem; border:1px solid var(--linea-forte); background:var(--carta);
  color:var(--inchiostro); cursor:pointer; box-shadow:0 1px 5px rgba(0,0,0,.2); }}
.penna button[aria-pressed="true"] {{ background:var(--inchiostro); color:var(--fondo);
  border-color:var(--inchiostro); }}
body.testi [contenteditable="true"] {{ outline:1px dashed var(--linea-forte);
  outline-offset:2px; }}
body.testi [contenteditable="true"]:focus {{ outline:2px solid var(--inchiostro);
  background:var(--carta); }}
body.testi .scheda.spenta {{ display:grid; opacity:.45; }}   /* niente resta nascosto */
/* i finti chip prendono le stesse classi dei veri, ma uno `<span>` nasce in linea */
body.testi span.chip {{ display:inline-block; }}

.prov {{ margin:1.2rem 0 0; font-family:var(--mono); font-size:.68rem; line-height:1.7;
  color:var(--tenue); }}
.prov b {{ font-weight:500; color:var(--inchiostro); }}
.vuoto {{ color:var(--tenue); font-family:var(--mono); font-size:.8rem;
  padding:2rem 0; display:none; }}

.assenti {{ margin-top:4rem; border-top:2px solid var(--inchiostro); padding-top:1.4rem; }}
.assenti h2 {{ font-size:1.25rem; }}
.gruppo {{ margin-top:2.2rem; }}
.gruppo h3 {{ font-family:var(--display); font-weight:600; font-size:.95rem; margin:0 0 .2rem; }}
.gruppo h3 small {{ font-family:var(--mono); font-weight:400; font-size:.7rem;
  color:var(--tenue); margin-left:.5rem; }}
.griglia {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(140px,1fr));
  gap:.7rem; margin-top:.9rem; }}
figure.assente {{ margin:0; }}
figure.assente img {{ width:100%; display:block; background:var(--pista); }}
figure.assente figcaption {{ font-family:var(--mono); font-size:.6rem; color:var(--tenue);
  padding-top:.25rem; font-variant-numeric:tabular-nums; }}

footer {{ margin-top:4rem; padding-top:1.4rem; border-top:1px solid var(--linea);
  font-size:.85rem; color:var(--tenue); max-width:66ch; }}
footer code {{ font-family:var(--mono); font-size:.78rem; color:var(--inchiostro); }}
/* ── banco di confronto e correzioni: solo nella pagina di lavoro ── */
.banco {{ position:sticky; top:0; z-index:20; background:var(--carta);
  border-bottom:2px solid var(--inchiostro); padding:.7rem 0 .8rem;
  margin:0 0 1.5rem; display:none; }}
.banco.aperto {{ display:block; }}
#guaio {{ background:var(--p5); color:#fff; padding:.5rem .7rem; margin:0 0 .6rem;
  font-family:var(--mono); font-size:.72rem; }}
#guaio[hidden] {{ display:none; }}
#fine {{ background:var(--inchiostro); color:var(--fondo); padding:.5rem .7rem;
  margin:0 0 .6rem; font-family:var(--mono); font-size:.72rem; }}
#fine[hidden] {{ display:none; }}
.schermi {{ display:grid; grid-template-columns:1fr 1fr; gap:.6rem; }}
.schermi figure {{ margin:0; position:relative; }}
.schermi video {{ width:100%; display:block; background:#000; aspect-ratio:16/9; }}
.schermi figcaption {{ position:absolute; top:.4rem; left:.4rem; background:var(--inchiostro);
  color:var(--fondo); padding:.1rem .45rem; font-family:var(--mono); font-size:.62rem; }}
.comandi {{ display:flex; flex-wrap:wrap; align-items:center; gap:.5rem; margin-top:.6rem;
  font-family:var(--mono); font-size:.72rem; }}
.comandi button, .comandi select {{ font-family:var(--mono); font-size:.72rem;
  padding:.3rem .6rem; border:1px solid var(--linea-forte); background:transparent;
  color:var(--inchiostro); cursor:pointer; }}
.comandi button.acceso {{ background:var(--inchiostro); color:var(--fondo);
  border-color:var(--inchiostro); }}
.comandi .sep {{ color:var(--tenue); }}
.comandi input[type=range] {{ width:9rem; accent-color:var(--inchiostro); }}
#dove {{ color:var(--tenue); font-variant-numeric:tabular-nums; }}
#scarto {{ margin-left:auto; color:var(--tenue); font-variant-numeric:tabular-nums; }}
#scarto.male {{ color:var(--p5); }}
.confronta {{ font-family:var(--mono); font-size:.68rem; padding:.2rem .5rem;
  border:1px solid var(--linea-forte); background:transparent; color:var(--inchiostro);
  cursor:pointer; }}
.confronta:hover, .comandi button:hover {{ border-color:var(--inchiostro); }}
.scheda.suona {{ box-shadow:inset 3px 0 0 var(--inchiostro); }}

.verdetti {{ display:none; gap:.35rem; margin-top:.7rem; }}
body.correzione .verdetti {{ display:flex; }}
.vd {{ font-family:var(--mono); font-size:.8rem; width:2rem; padding:.2rem 0;
  border:1px solid var(--linea-forte); background:transparent; color:var(--inchiostro);
  cursor:pointer; }}
.vd.scelto[data-v=giusto] {{ background:var(--p3); border-color:var(--p3); color:#fff; }}
.vd.scelto[data-v=sbagliato] {{ background:var(--p5); border-color:var(--p5); color:#fff; }}
.vd.scelto[data-v=incerto] {{ background:var(--p1); border-color:var(--p1); color:#fff; }}
body.correzione .descr, body.correzione .dial {{ outline:1px dashed var(--linea-forte);
  outline-offset:.3rem; min-height:1.4em; }}
body.correzione .descr:focus, body.correzione .dial:focus {{
  outline:2px solid var(--inchiostro); }}
/* Uno shot senza descrizione o senza trascrizione deve comunque offrire **dove scrivere**:
   in lettura resta un segnaposto tenue, in correzione è una casella vuota come le altre.
   Il segnaposto è un pseudo-elemento, quindi non finisce nel testo che si esporta. */
body.correzione .parlato {{ }}   /* in correzione la tendina si apre da sé, vedi il JS */
.descr:empty::before {{ content:"nessuna descrizione"; opacity:.45; font-style:italic; }}
body.correzione .descr:empty::before {{ content:"scrivi la descrizione…"; }}
body.correzione .dial:empty::before {{ content:"scrivi la trascrizione…"; opacity:.45; }}
.descr:empty:focus::before, .dial:empty:focus::before {{ content:""; }}
.accoppiato {{ font-family:var(--mono); font-size:.7rem; color:var(--tenue);
  margin:.1rem 0 .5rem !important; }}
.accoppiato b {{ color:var(--inchiostro); font-weight:500; }}
.descr.toccata {{ background:color-mix(in srgb, var(--p1) 14%, transparent); }}
.barra-corr {{ display:flex; gap:.5rem; align-items:center; margin:0 0 1.2rem;
  font-family:var(--mono); font-size:.72rem; }}
.barra-corr button {{ font-family:var(--mono); font-size:.72rem; padding:.3rem .6rem;
  border:1px solid var(--linea-forte); background:transparent; color:var(--inchiostro);
  cursor:pointer; }}
.barra-corr button.acceso {{ background:var(--inchiostro); color:var(--fondo); }}
#conta {{ color:var(--tenue); }}
#conta.vive {{ color:var(--p5); font-weight:500; }}

@media (max-width:760px) {{
  .schermi {{ grid-template-columns:1fr; }}
  .scheda {{ grid-template-columns:1fr; }}
  details.assenti ul {{ columns:1; }}
}}
@media (prefers-reduced-motion:reduce) {{ * {{ transition:none !important; }} }}
</style>
{"</head>" + chr(10) + "<body>" if autonoma else ""}
<div class="penna">
  <button id="penna" aria-pressed="false" title="modifica i testi della pagina"
   aria-label="modifica i testi della pagina">✎</button>
  <button id="penna-conta" hidden title="scarica i testi cambiati">↓ 0</button>
  <button id="penna-azzera" hidden title="rimetti i testi originali">↺</button>
</div>
<div class="foglio">
{banco}
<header class="testata">
  <div class="occhiello">Grifi · Sarchielli, 1975 — montato contro girato</div>
  <h1>Anna nel <em>Fuori campo</em></h1>
  <p class="sommario">Il film uscito in sala dura 3 ore e 34. Il girato in cui si cerca ne
  dura {int(girato//3600)} e {int(girato%3600//60):02d}: le cinque parti trasmesse da Fuori
  Orario che sono materiale — la sesta è un rimontaggio delle altre ed è esclusa. Questa
  pagina dice, per ogni pezzo del montato, dove sta nel girato — e quali pezzi non ci
  sono.</p>
</header>

<div class="cifre">
  <div class="cifra"><b>{tot/60:.0f} min</b><span>di film ritrovati</span></div>
  <div class="cifra"><b>{tot/durata_film:.0%}</b><span>del montaggio</span></div>
  <div class="cifra"><b>{len(trovati)}/{len(righe)}</b><span>shot agganciati</span></div>
  <div class="cifra"><b>{len(segs)}</b><span>segmenti distinti</span></div>
</div>

<h2>Dove ricade il montaggio</h2>
<p class="guida">La barra alta è il film, dal primo all'ultimo fotogramma. Sotto, le cinque
parti del <i>Fuori campo</i> in cui si è cercato: ogni tacca è un pezzo che ricompare nel
montato, colorato secondo la parte da cui viene. Clicca una tacca per andare alla scheda.</p>

<div class="riga film"><div class="et"><span class="nome">Il film</span>
  <span class="dur">{hms(durata_film)}</span></div>
  <div class="pista">{film_bar}</div><span class="quota">{tot/durata_film:.0%}</span></div>
<div class="riga vuoti"><div class="et"><span class="nome">Non ritrovato</span>
  <span class="dur">{(durata_film - tot)/60:.0f} min</span></div>
  <div class="pista">{barra_vuoti}</div><span class="quota">{1 - tot/durata_film:.0%}</span></div>
<div class="legenda">
  <button class="leg" data-t="scena" aria-pressed="false" title="mostra solo le scene vere">
   <i style="background:var(--manca-scena)"></i>scene vere · {minuti_tipo["scena"]:.1f} min</button>
  <button class="leg" data-t="cartello" aria-pressed="false" title="mostra solo cartelli e didascalie">
   <i style="background:var(--manca-cartello)"></i>cartelli e didascalie · {minuti_tipo["cartello"]:.1f} min</button>
  <button class="leg" data-t="nero" aria-pressed="false" title="mostra solo i fotogrammi neri">
   <i style="background:var(--manca-nero)"></i>fotogrammi neri · {minuti_tipo["nero"]:.1f} min</button>
</div>
<div class="scala"><span>0:00:00</span><span>{hms(durata_film/2)}</span><span>{hms(durata_film)}</span></div>
{"".join(righe_girato)}

{barra_corr}
<div class="filtri">
  <button class="chip" aria-pressed="true" data-p="0">tutte</button>
  {"".join(f'<button class="chip" aria-pressed="false" data-p="{p}">{etichetta(p, True)}</button>'
            for p in PARTI if any(s["parte"] == p for s in segs))}
  <button class="chip" id="ordina" aria-pressed="false"
   title="i segmenti che il controllo non conferma, per primi">dubbi in cima</button>
  {'<button class="chip" id="assenti-su" aria-pressed="false"'
   ' title="porta in cima gli shot che nel girato non ci sono">non trovati in cima</button>'
   if mancanti else ''}
  <div class="ricerche">
   <input class="cerca" id="cerca-descr" type="search" placeholder="cerca nelle descrizioni…"
    aria-label="cerca nelle descrizioni">
   <input class="cerca" id="cerca-dial" type="search" placeholder="cerca nel parlato…"
    aria-label="cerca nel parlato">
  </div>
</div>

<div class="schede">{"".join(schede)}</div>
<p class="vuoto">Nessuno shot corrisponde a questi filtri.</p>

<section class="assenti">
  <h2>Quello che il girato non contiene</h2>
  <p class="guida">{len(mancanti)} shot su {len(righe)} non si ritrovano nel girato, per
  {sum(sh["end_time"] - sh["start_time"] for sh in mancanti)/60:.0f} minuti. Tre quarti sono
  cartelli e neri, che nel materiale girato non possono esserci per definizione.</p>
  {voci_mancanti}
</section>

<footer>{istruzioni}Accoppiamento per impronta visiva, un vettore ogni mezzo secondo, cinque scale di
ritaglio — il girato mostra più campo del montato, e di quanto cambia da ripresa a ripresa.
Un match vale solo dentro una corsa in cui le due sorgenti avanzano insieme. Precisione
misurata, non stimata: ogni segmento è ripreso a piena risoluzione cercando zoom e posizione, e
{verificati} su {len(segs)} stanno sopra il massimo di quaranta accoppiamenti casuali. I confini
valgono ±1 s.{provenienza()}</footer>
</div>

<script>
// Un errore qui dentro spegne tutti i comandi della pagina, e da fuori si vede solo che
// «non funziona niente». Questo riquadro dice cosa è successo, invece di lasciare indovinare.
addEventListener('error', ev => {{
  const g = document.getElementById('guaio');
  if (!g) return;
  const b = document.getElementById('banco');
  if (b) b.classList.add('aperto');
  g.hidden = false;
  if (ev.target && ev.target.tagName === 'VIDEO') {{
    const e = ev.target.error;
    const nome = decodeURIComponent((ev.target.currentSrc || ev.target.src).split('/').pop());
    g.textContent = 'Manca ' + nome + ': per vedere i filmati serve una cartella «video» '
      + 'accanto a questo file: i filmati vanno messi lì accanto, oppure in una cartella '
      + 'chiamata ANNA o video. Servono Anna.mp4 (il montaggio) e «Fuori campo di Anna - 1.mp4» '
      + 'fino alla 5. Tutto il resto della pagina funziona lo stesso.';
  }} else {{
    g.textContent = 'Errore JavaScript: ' + ev.message + '  (' + (ev.lineno || '?') + ')'
      + ' — i comandi della pagina sono fermi.';
  }}
}}, true);

const schede = [...document.querySelectorAll('.scheda')];
let parte = 0, cerca = '', parlato = '';
function applica() {{
  let n = 0;
  for (const s of schede) {{
    const ok = (parte === 0 || +s.dataset.parte === parte)
      && (cerca === '' || s.dataset.testo.includes(cerca))
      && (parlato === '' || (s.dataset.parlato || '').includes(parlato));
    s.classList.toggle('spenta', !ok);
    if (ok) n++;
  }}
  document.querySelector('.vuoto').style.display = n ? 'none' : 'block';
}}
document.querySelectorAll('.chip').forEach(c => c.onclick = () => {{
  parte = +c.dataset.p;
  document.querySelectorAll('.chip').forEach(o =>
    o.setAttribute('aria-pressed', o === c ? 'true' : 'false'));
  applica();
}});
const ordina = document.getElementById('ordina');
if (ordina) ordina.onclick = () => {{
  const su = ordina.getAttribute('aria-pressed') !== 'true';
  ordina.setAttribute('aria-pressed', su ? 'true' : 'false');
  // `.schede` e non `.foglio`: riappendere alla madre sbagliata spediva le schede in fondo
  // alla pagina, dopo la sezione degli assenti e dopo il footer
  const madre = document.querySelector('.schede');
  const chiave = s => su ? +s.dataset.ctrl : +s.dataset.shot;
  [...schede].sort((a, b) => chiave(a) - chiave(b)).forEach(s => madre.appendChild(s));
}};
// «non trovati in cima» sposta la sezione degli assenti, non riordina le schede: gli shot
// senza aggancio non hanno una scheda — non c'è un girato da metterci accanto. `.vuoto` è
// l'ancora per rimetterla al suo posto, perché è l'unico elemento qui che non si muove mai.
const suGiu = document.getElementById('assenti-su');
if (suGiu) suGiu.onclick = () => {{
  const su = suGiu.getAttribute('aria-pressed') !== 'true';
  suGiu.setAttribute('aria-pressed', su ? 'true' : 'false');
  const assenti = document.querySelector('.assenti'), vuoto = document.querySelector('.vuoto');
  if (su) document.querySelector('.schede').before(assenti);
  else vuoto.after(assenti);
}};
document.getElementById('cerca-descr').oninput = ev => {{
  cerca = ev.target.value.trim().toLowerCase();
  applica();
}};
document.getElementById('cerca-dial').oninput = ev => {{
  parlato = ev.target.value.trim().toLowerCase();
  applica();
}};
document.querySelectorAll('.sg').forEach(b => b.onclick = () => {{
  const k = b.dataset.k;
  document.querySelectorAll('.sg.viva').forEach(o => o.classList.remove('viva'));
  document.querySelectorAll('.sg[data-k="' + k + '"]').forEach(o => o.classList.add('viva'));
  const s = b.dataset.shot && document.getElementById('shot-' + b.dataset.shot);
  if (s) {{
    if (s.classList.contains('spenta')) {{
      parte = 0; cerca = ''; parlato = '';
      document.querySelectorAll('.cerca').forEach(c => c.value = '');
      document.querySelectorAll('.chip').forEach(o =>
        o.setAttribute('aria-pressed', o.dataset.p === '0' ? 'true' : 'false'));
      applica();
    }}
    document.querySelectorAll('.scheda.viva').forEach(o => o.classList.remove('viva'));
    s.classList.add('viva');
    s.scrollIntoView({{behavior:'smooth', block:'center'}});
  }}
}});
// I tre quadratini della legenda isolano un tipo di buco nella barra del non ritrovato.
// Ripremendo quello acceso si torna a vederli tutti: un filtro che non si sa spegnere è una
// trappola, e qui non c'è un bottone «tutte» come fra i chip.
let tipoVuoto = '';
document.querySelectorAll('.leg').forEach(l => l.onclick = () => {{
  tipoVuoto = tipoVuoto === l.dataset.t ? '' : l.dataset.t;
  document.querySelectorAll('.leg').forEach(o =>
    o.setAttribute('aria-pressed', o.dataset.t === tipoVuoto ? 'true' : 'false'));
  document.querySelectorAll('button.vt').forEach(v =>
    v.hidden = tipoVuoto !== '' && v.dataset.t !== tipoVuoto);
}});
// ── modifica dei testi della pagina ────────────────────────────────────────────
// Tutto dentro una funzione: la pagina ha **un solo** `<script>`, e un nome ripetito qui
// (`insieme` esisteva già) non rompe questo blocco — rompe l'intero script, filtri e
// player compresi, con il sintomo «nessun bottone funziona».
(() => {{
// «Tutte le scritte» vuol dire ogni elemento che porta testo e **non contiene blocchi**: i
// figli in linea (`<b>`, `<i>`, `<code>`) viaggiano col genitore, così una frase resta una
// frase invece di spezzarsi in tre caselle. I bottoni contano come testo — anche le
// etichette dei filtri si possono riscrivere — e per questo mentre si scrive i loro clic
// vengono fermati in cattura: senza, premere «FC3» filtrerebbe invece di posare il cursore.
const T_CHIAVE = 'fuoricampo-testi';
const foglio = document.querySelector('.foglio');
const VIETATI = new Set(['SCRIPT', 'STYLE', 'IMG', 'VIDEO', 'INPUT', 'SELECT', 'OPTION']);
// Il criterio guarda **chi porta il testo**, non il `display`: dentro un contenitore flex i
// figli vengono blocchificati, quindi l'`<i>` del pallino colorato risultava «blocco» e la
// voce della legenda restava fuori dalle scritte modificabili. La disposizione non c'entra
// niente con la domanda, ed era un modo di chiederla che dipendeva dal CSS.
const testoProprio = e =>
  [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
const candidati = [...foglio.querySelectorAll('*')].filter(e =>
  !VIETATI.has(e.tagName) && e.textContent.trim()
  && (testoProprio(e) || ![...e.children].some(c => c.textContent.trim())));
// un elemento dentro un altro già scrivibile sarebbe una casella dentro una casella
const insieme = new Set(candidati);
const scrivibili = candidati.filter(e => {{
  for (let a = e.parentElement; a && a !== foglio; a = a.parentElement)
    if (insieme.has(a)) return false;
  return true;
}});

// La chiave è il **testo originale**, non la posizione: se un run nuovo cambia una frase, la
// correzione vecchia non si applica invece di finire su una frase che non è la sua. È la
// stessa regola di `merge_prior` e di `applica_correzioni.py`, che accoppiano per
// `start_frame` e mai per indice.
const visti = {{}};
const chiave = e => {{
  const base = e.tagName + '|' + e.textContent.trim().slice(0, 120);
  visti[base] = (visti[base] || 0) + 1;
  return base + '|' + visti[base];
}};
const chiavi = new Map(), originali = new Map();
for (const e of scrivibili) {{ chiavi.set(e, chiave(e)); originali.set(e, e.innerHTML); }}

const testi = {{}};
const contaT = document.getElementById('penna-conta');
const azzeraT = document.getElementById('penna-azzera');
function contaTesti() {{
  const n = Object.keys(testi).length;
  contaT.textContent = '↓ ' + n;
  contaT.hidden = azzeraT.hidden = n === 0;
  try {{ localStorage.setItem(T_CHIAVE, JSON.stringify(testi)); }} catch (e) {{}}
}}
function segnaTesto(vero, html) {{
  const k = chiavi.get(vero);
  if (html === originali.get(vero)) delete testi[k];
  else testi[k] = {{originale: originali.get(vero), nuovo: html}};
  contaTesti();
}}
for (const e of scrivibili) e.addEventListener('input', () => segnaTesto(e, e.innerHTML));

// Un `<button>` è un comando: il clic gli dà il **fuoco**, e su un controllo di form il
// browser non ci posa il cursore di scrittura — `contenteditable` sul bottone regge le
// modifiche fatte da codice (provato: `insertText` entra) ma non c'è modo di garantire che
// entri anche una battitura vera. Invece di dipendere da quel dettaglio, mentre si scrive il
// bottone si **toglie**: il nodo vero resta da parte coi suoi gestori attaccati e al suo
// posto va uno `<span>` con le stesse classi, che è un elemento qualsiasi e il cursore lo
// prende di sicuro. Vale per le etichette che sono testo d'autore — i filtri e la legenda —
// non per i comandi delle schede, che sono glifi (▶ ✓ ✗ ?).
const SCAMBIABILI = '.chip, .leg';
const scambiati = new Map();
function scambia(on) {{
  if (on) {{
    for (const b of foglio.querySelectorAll(SCAMBIABILI)) {{
      const s = document.createElement('span');
      s.className = b.className;
      s.contentEditable = 'true';
      s.innerHTML = b.innerHTML;
      s.addEventListener('input', () => segnaTesto(b, s.innerHTML));
      b.replaceWith(s);
      scambiati.set(s, b);
    }}
  }} else {{
    for (const [s, b] of scambiati) {{ b.innerHTML = s.innerHTML; s.replaceWith(b); }}
    scambiati.clear();
  }}
}}
document.getElementById('penna').onclick = ev => {{
  const on = document.body.classList.toggle('testi');
  ev.currentTarget.setAttribute('aria-pressed', on ? 'true' : 'false');
  for (const e of scrivibili) e.contentEditable = on ? 'true' : 'false';
  scambia(on);
}};
// solo `stopPropagation`: `preventDefault` toglierebbe anche la possibilità di posare il
// cursore dentro il bottone, che è proprio quello che serve qui
document.addEventListener('click', ev => {{
  if (document.body.classList.contains('testi') && foglio.contains(ev.target))
    ev.stopPropagation();
}}, true);
contaT.onclick = () => {{
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(
    {{generato: new Date().toISOString(), testi: Object.values(testi)}}, null, 1)],
    {{type: 'application/json'}}));
  a.download = 'testi.json';
  a.click();
  URL.revokeObjectURL(a.href);
}};
azzeraT.onclick = () => {{
  for (const e of scrivibili) e.innerHTML = originali.get(e);
  for (const k of Object.keys(testi)) delete testi[k];
  contaTesti();
}};
try {{
  const vecchi = JSON.parse(localStorage.getItem(T_CHIAVE) || '{{}}');
  for (const e of scrivibili) {{
    const v = vecchi[chiavi.get(e)];
    if (v && v.originale === originali.get(e)) {{
      e.innerHTML = v.nuovo;
      testi[chiavi.get(e)] = v;
    }}
  }}
  contaTesti();
}} catch (e) {{}}
}})();
{lavoro_js}
</script>{chiudi}"""


def dati():
    """Il trittico che serve a costruire la pagina, comune ai tre modi."""
    segs = con_controllo(json.loads((QUI / "segmenti-video.json").read_text()))
    man = json.loads(MANIFEST.read_text())
    shots = man["shots"]
    for sc in man.get("scenes", []):
        for i in range(sc["first_shot"], sc["last_shot"] + 1):
            if i < len(shots):
                shots[i]["scena"] = sc["index"]
    righe = per_shot(shots, segs)
    tipo = classifica(shots)          # su tutti: i buchi stanno anche dentro shot agganciati
    for sh in shots:
        sh["classe"] = tipo.get(sh["index"], "scena")
    return righe, segs, man, durate_girato()


if __name__ == "__main__":
    # `dati()` e non una copia: quando la classificazione degli shot è stata aggiunta lì, qui
    # è rimasto il codice vecchio — e le pagine offline e web sono uscite senza `classe`, con
    # ogni buco caduto nel default «scena» e i gruppi in fondo vuoti. Una funzione sola.
    righe, segs, man, durate = dati()
    modo = "offline" if "--offline" in sys.argv else "artifact"
    out = QUI / ("Anna nel Fuori campo.html" if modo == "offline" else "anna-fuoricampo.html")
    pagina = costruisci(righe, segs, man["duration"], durate, modo)
    controlla_js(pagina)
    out.write_text(pagina)
    print(f"{out.name}  {out.stat().st_size/1e6:.1f} MB"
          + ("  (font inclusi, nessuna richiesta di rete)" if modo == "offline" else ""))
