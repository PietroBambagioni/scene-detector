"""Da `segmenti.json` alla timeline HTML e alla relazione testuale.

Gli shot e le loro descrizioni non si ricalcolano: stanno già in `clips/Anna/manifest.json`,
prodotto dalla pipeline sul film. Qui si incrociano con i segmenti ritrovati nel girato.

    .venv/bin/python fuoricampo/timeline.py [--miniature]
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from impronta import PARTI

QUI = Path(__file__).parent
RADICE = QUI.parent          # `fuoricampo/` sta alla radice del repo
MANIFEST = RADICE / "clips" / "Anna" / "manifest.json"
GIRATO = Path("/Users/pietrobambagioni/Desktop/cartella senza nome/anna film")
# stessa famiglia fredda della pagina principale: i caldi restano al non ritrovato
COLORI = ["#1F8A9E", "#218A66", "#4C8A26", "#3D6FC4", "#6C5CD4", "#A855A0"]


def etichetta(p: int, breve: bool = False) -> str:
    """Come si chiama una parte del girato nelle pagine.

    FC1 non è girato e chiamarlo «Fuori campo 1» faceva sembrare un buco del metodo il suo
    0%: è la **presentazione al festival** — il dibattito con Grifi e Sarchielli dopo la
    proiezione, tavolo, microfoni e pubblico, con in apertura i cartelli sul restauro. Nel
    parlato si sente da dove viene («la copia è stata pagata dalla Biennale di Venezia»,
    «il risultato tecnico a cui abbiamo assistito questa sera durante la proiezione»).
    Non contiene un fotogramma del film perché non ne contiene per costruzione.
    """
    if p == 1:
        return "presentazione" if breve else "Presentazione al festival"
    return f"FC{p}" if breve else f"Fuori campo {p}"


def hms(s: float) -> str:
    s = int(round(s))
    return f"{s//3600}:{s%3600//60:02d}:{s%60:02d}"


def durate_girato() -> dict[int, float]:
    return {p: float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
         str(GIRATO / f"Fuori campo di Anna - {p}.mp4")],
        capture_output=True, text=True, check=True).stdout.strip()) for p in PARTI}


def sovrapposizione(a0, a1, b0, b1) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def copertura(intervalli) -> float:
    """Secondi coperti dall'**unione** degli intervalli, non dalla somma delle durate.

    Dopo `estendi.py` i segmenti vicini si allungano l'uno verso l'altro e si sovrappongono:
    sommare le durate dava 260 minuti su un film che ne dura 214, cioè «122% del montaggio
    ritrovato». La somma dice quanto materiale è stato accoppiato — e va bene per capire se
    un pezzo di film ricorre in più punti del girato; solo l'unione dice quanto film è coperto.
    """
    iv = sorted(intervalli)
    tot, fine = 0.0, -1.0
    for a, b in iv:
        a = max(a, fine)
        if b > a:
            tot += b - a
        fine = max(fine, b)
    return tot


REGISTRO = QUI / "run.json"


def annota_passo(passo: str, segs: list[dict], **campi) -> None:
    """Registra in `run.json` chi ha prodotto i segmenti che stanno su disco, e quando.

    La provenienza la scrive chi produce il dato, non chi disegna la pagina. Le soglie in
    `match.py` si toccano fra un run e l'altro: una pagina che leggesse i parametri *di
    adesso* invece di quelli del run li dichiarerebbe sbagliati proprio quando servono, cioè
    quando il file è già in giro per posta e nessuno può più risalire a com'era il codice.

    Un passo rilanciato sostituisce la sua riga invece di aggiungerne una seconda: il
    registro dice da dove viene il file che c'è, non quante volte ci si è provato.
    """
    reg = json.loads(REGISTRO.read_text()) if REGISTRO.exists() else {"passi": []}
    reg.update(campi)
    reg["passi"] = [x for x in reg["passi"] if x["passo"] != passo] + [{
        "passo": passo,
        "quando": datetime.now().astimezone().isoformat(timespec="seconds"),
        "n": len(segs),
        "copertura_min": round(copertura((s["film_start"], s["film_end"]) for s in segs) / 60, 1),
    }]
    REGISTRO.write_text(json.dumps(reg, indent=1, ensure_ascii=False))


# Un segmento che sfiora il bordo dello shot accanto non lo ha ritrovato: lo tocca. Senza
# questi minimi, 188 agganci su 420 stavano sotto il 15% di copertura e 40 shot risultavano
# «ritrovati» per uno sfioramento di qualche centesimo di secondo.
MIN_COPERTO_S = 1.0
MIN_COPERTO_FRAZ = 0.10


def con_controllo(segs: list[dict]) -> list[dict]:
    """Aggiunge a ogni segmento il punteggio di `controllo.py`, se è stato calcolato.

    L'accoppiamento è per (inizio nel film, parte), non per posizione nella lista: i due file
    si rigenerano in momenti diversi e l'ordine non è un'identità — la stessa regola per cui
    gli shot si accoppiano per `start_frame`.
    """
    f = QUI / "controllo.json"
    if not f.exists():
        return segs
    voti = {(round(c["film_start"], 2), c["parte"]): c.get("controllo")
            for c in json.loads(f.read_text())}
    for s in segs:
        v = voti.get((round(s["film_start"], 2), s["parte"]))
        if v is not None:
            s["controllo"] = v
    return segs


def per_shot(shots, segs):
    """A ogni shot del film i segmenti di girato che lo coprono, dal più esteso."""
    out = []
    for sh in shots:
        t0, t1 = sh["start_time"], sh["end_time"]
        durata = max(t1 - t0, 1e-6)
        trovati = []
        for sg in segs:
            ov = sovrapposizione(t0, t1, sg["film_start"], sg["film_end"])
            if ov < MIN_COPERTO_S or ov / durata < MIN_COPERTO_FRAZ:
                continue
            # il pezzo di girato che corrisponde a QUESTO shot, non all'intero segmento.
            # `film_da`/`film_a` delimitano l'intersezione: i fotogrammi di confronto vanno
            # presi lì e non al centro dello shot, che con una copertura parziale cade fuori
            # dalla parte coperta e mostra due immagini che non si corrispondono.
            d0 = max(t0, sg["film_start"]) - sg["film_start"]
            d1 = min(t1, sg["film_end"]) - sg["film_start"]
            trovati.append({
                "parte": sg["parte"], "score": sg["score"], "coperto": ov,
                "controllo": sg.get("controllo"),
                "film_da": max(t0, sg["film_start"]), "film_a": min(t1, sg["film_end"]),
                "girato_start": sg["girato_start"] + d0,
                "girato_end": sg["girato_start"] + d1,
            })
        trovati.sort(key=lambda x: -x["coperto"])
        # unione, non somma: dopo `estendi.py` due segmenti possono coprire lo stesso pezzo di
        # shot, e sommando si ottiene «coperto 142%»
        out.append((sh, trovati,
                    min(copertura((t["film_da"], t["film_a"]) for t in trovati) / durata, 1.0)))
    return out


def miniature(righe, durate):
    """Un frame del film e il suo corrispondente nel girato, per verificare a occhio."""
    d = QUI / "thumbs"
    d.mkdir(exist_ok=True)
    for sh, trovati, _ in righe:
        if not trovati:
            # anche gli shot mai ritrovati vanno mostrati: sono la parte del film che il
            # girato non contiene, ed è un risultato quanto gli altri
            nome = f"f{sh['index']:03d}.jpg"
            if not (d / nome).exists():
                subprocess.run(["ffmpeg", "-v", "error", "-ss",
                                f"{(sh['start_time'] + sh['end_time']) / 2:.2f}",
                                "-i", str(RADICE / "Film" / "Anna.mp4"), "-frames:v", "1",
                                "-vf", "scale=200:-1", "-y", str(d / nome)], check=True)
            continue
        t = trovati[0]
        coppie = [
            (RADICE / "Film" / "Anna.mp4", (t["film_da"] + t["film_a"]) / 2, f"f{sh['index']:03d}.jpg"),
            (GIRATO / f"Fuori campo di Anna - {t['parte']}.mp4",
             (t["girato_start"] + t["girato_end"]) / 2, f"g{sh['index']:03d}.jpg"),
        ]
        for src, ts, nome in coppie:
            if (d / nome).exists():
                continue
            subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ts:.2f}", "-i", str(src),
                            "-frames:v", "1", "-vf", "scale=200:-1", "-y", str(d / nome)], check=True)


def relazione(righe, segs, durata_film, durate):
    coperto = copertura((s["film_start"], s["film_end"]) for s in segs)
    r = [f"# Anna nel Fuori campo\n",
         f"Film: {hms(durata_film)} · girato: {hms(sum(durate.values()))} in 6 parti.",
         f"Ritrovati **{len(segs)} segmenti**, "
         f"{coperto/60:.0f} min di film ({coperto/durata_film:.0%}).\n",
         "## Scene del film e dove stanno nel girato\n"]
    scena_corrente = None
    for sh, trovati, cop in righe:
        if not trovati:
            continue
        if sh.get("scena") != scena_corrente:
            scena_corrente = sh.get("scena")
            r.append(f"\n### Scena {scena_corrente}\n")
        t = trovati[0]
        r.append(f"**Shot {sh['index']:03d}** · film {hms(sh['start_time'])}–{hms(sh['end_time'])} "
                 f"→ **Fuori campo {t['parte']}, {hms(t['girato_start'])}–{hms(t['girato_end'])}** "
                 f"· coperto {cop:.0%} · corr {t['score']:.2f}")
        if len(trovati) > 1:
            altri = ", ".join(f"{etichetta(a['parte'], True)} {hms(a['girato_start'])}" for a in trovati[1:4])
            r.append(f"   - anche in: {altri}")
        if sh.get("description"):
            r.append(f"   > {sh['description']}")
        r.append("")

    mancanti = [sh for sh, tr, _ in righe if not tr]
    r.append(f"\n## Shot del film non ritrovati nel girato ({len(mancanti)} su {len(righe)})\n")
    for sh in mancanti:
        r.append(f"- Shot {sh['index']:03d} · {hms(sh['start_time'])}–{hms(sh['end_time'])}"
                 + (f" · {sh['description'][:90]}…" if sh.get("description") else ""))
    return "\n".join(r)


def barra(segs, durata, chiave_start, chiave_end, colore_di, id_di):
    p = []
    for k, s in enumerate(segs):
        x = s[chiave_start] / durata * 100
        w = max((s[chiave_end] - s[chiave_start]) / durata * 100, 0.08)
        p.append(f'<i class="s" style="left:{x:.4f}%;width:{w:.4f}%;background:{colore_di(s)}" '
                 f'data-k="{id_di(s, k)}" title="{hms(s[chiave_start])}–{hms(s[chiave_end])} · corr {s["score"]}"></i>')
    return "".join(p)


def html(righe, segs, durata_film, durate, con_miniature):
    film_bar = barra(segs, durata_film, "film_start", "film_end",
                     lambda s: COLORI[(s["parte"] - 1) % 6], lambda s, k: k)
    barre_girato = []
    for p in PARTI:
        sp = [s for s in segs if s["parte"] == p]
        idx = {id(s): segs.index(s) for s in sp}
        barre_girato.append(
            f'<div class="riga"><label>{etichetta(p)} <small>{hms(durate[p])}</small></label>'
            f'<div class="bar">{barra(sp, durate[p], "girato_start", "girato_end", lambda s: COLORI[(p-1)%6], lambda s,k: idx[id(s)])}</div></div>')

    trovati = [(sh, tr, c) for sh, tr, c in righe if tr]
    voci = []
    for sh, tr, cop in trovati:
        t = tr[0]
        im = (f'<div class="mini"><img src="thumbs/f{sh["index"]:03d}.jpg" alt=""><img src="thumbs/g{sh["index"]:03d}.jpg" alt=""></div>'
              if con_miniature else "")
        voci.append(
            f'<article><header><b>Shot {sh["index"]:03d}</b>'
            f'<span class="t">{hms(sh["start_time"])}–{hms(sh["end_time"])}</span>'
            f'<span class="fr" style="background:{COLORI[(t["parte"]-1)%6]}">{etichetta(t["parte"], True)} · {hms(t["girato_start"])}–{hms(t["girato_end"])}</span>'
            f'<span class="c">{cop:.0%} · corr {t["score"]:.2f}</span></header>{im}'
            f'<p>{sh.get("description","")}</p></article>')

    tot = copertura((s["film_start"], s["film_end"]) for s in segs)
    return f"""<!doctype html><meta charset="utf-8"><title>Anna nel Fuori campo</title>
<style>
:root{{color-scheme:light dark}}
body{{font:14px/1.5 system-ui,sans-serif;margin:0;padding:2rem;max-width:1100px;margin:auto;
 background:Canvas;color:CanvasText}}
h1{{font-size:1.4rem;margin:0 0 .2rem}}
.sub{{opacity:.65;margin:0 0 2rem}}
.riga{{display:flex;align-items:center;gap:.6rem;margin:.35rem 0}}
label{{width:11rem;flex:none;font-size:.8rem;text-align:right}}
label small{{opacity:.5}}
.bar{{position:relative;height:22px;flex:1;background:color-mix(in srgb,CanvasText 8%,Canvas);border-radius:3px}}
.bar.film{{height:34px}}
i.s{{position:absolute;top:0;bottom:0;cursor:pointer;border-radius:1px}}
i.s.on{{outline:2px solid CanvasText;outline-offset:1px;z-index:2}}
.scala{{display:flex;justify-content:space-between;font-size:.7rem;opacity:.5;margin:.2rem 0 1.4rem 11.6rem}}
article{{border-top:1px solid color-mix(in srgb,CanvasText 15%,Canvas);padding:.9rem 0}}
header{{display:flex;gap:.7rem;align-items:center;flex-wrap:wrap}}
.t{{opacity:.6}}
.fr{{color:#fff;padding:.1rem .45rem;border-radius:3px;font-size:.78rem}}
.c{{margin-left:auto;opacity:.55;font-size:.8rem}}
.mini{{display:flex;gap:.4rem;margin:.5rem 0}}
.mini img{{width:200px;border-radius:3px}}
p{{margin:.4rem 0 0;opacity:.8;max-width:75ch}}
</style>
<h1>Anna nel <i>Fuori campo</i></h1>
<p class="sub">{len(segs)} segmenti · {tot/60:.0f} min di film ritrovati nel girato
 ({tot/durata_film:.0%} del montato) · {len(trovati)} shot su {len(righe)}</p>

<div class="riga"><label><b>Film</b> <small>{hms(durata_film)}</small></label>
 <div class="bar film">{film_bar}</div></div>
<div class="scala"><span>0:00:00</span><span>{hms(durata_film/2)}</span><span>{hms(durata_film)}</span></div>
{"".join(barre_girato)}
<h2 style="font-size:1rem;margin:2.5rem 0 0">Scene ritrovate</h2>
{"".join(voci)}
<script>
document.querySelectorAll('i.s').forEach(e=>e.onclick=()=>{{
  const k=e.dataset.k, on=e.classList.contains('on');
  document.querySelectorAll('i.s.on').forEach(x=>x.classList.remove('on'));
  if(!on) document.querySelectorAll(`i.s[data-k="${{k}}"]`).forEach(x=>x.classList.add('on'));
}});
</script>"""


if __name__ == "__main__":
    segs = json.loads((QUI / "segmenti-video.json").read_text())
    man = json.loads(MANIFEST.read_text())
    shots = man["shots"]
    for sc in man.get("scenes", []):
        for i in range(sc["first_shot"], sc["last_shot"] + 1):
            if i < len(shots):
                shots[i]["scena"] = sc["index"]

    durate = durate_girato()
    righe = per_shot(shots, segs)
    con_mini = "--miniature" in sys.argv
    if con_mini:
        miniature(righe, durate)
    (QUI / "relazione.md").write_text(relazione(righe, segs, man["duration"], durate))
    (QUI / "timeline.html").write_text(html(righe, segs, man["duration"], durate, con_mini))
    print(f"timeline.html · relazione.md · {sum(1 for _,t,_ in righe if t)}/{len(righe)} shot ritrovati")
