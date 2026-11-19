"""L'altra metà della domanda: che cosa del girato **non** è finito nel film.

`artifact.py` racconta il montato — per ogni pezzo, dove sta nel ciak. Il rovescio non lo
dice nessuno, ed è la parte grossa: delle dodici ore e mezza di girato trasmesse, nove e
mezza non compaiono nel film. Sono i pezzi che Grifi ha scartato, cioè il *fuori campo* nel
senso proprio, e finora esistevano solo come spazio vuoto fra due tacche di una barra.

Il dato è già tutto in `segmenti-video.json`: basta prendere il **complemento** degli
intervalli usati, parte per parte. Il lavoro vero è renderlo guardabile — un blocco di
novanta minuti descritto da un fotogramma solo non è guardabile — quindi ogni blocco prende
una miniatura ogni due minuti, fino a dieci.

**FC1 non conta come scartato**: non è girato, è la presentazione al festival. Comparirebbe
come il blocco più lungo di tutti e falserebbe la cifra in testa.

    .venv/bin/python fuoricampo/scartato.py [--miniature]
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from artifact import b64, controlla_js, font_incorporati, provenienza, stile_comune
from impronta import PARTI
from timeline import GIRATO, QUI, durate_girato, etichetta, hms

MINI = QUI / "thumbs-scartato"
MIN_BLOCCO = 30.0     # sotto i trenta secondi è uno stacco fra due riusi, non un pezzo scartato
OGNI = 120.0          # una miniatura ogni due minuti di blocco…
MAX_MINI = 10         # …ma non più di dieci: oltre, la striscia non si legge più
SCARTABILI = [p for p in PARTI if p != 1]   # FC1 è la presentazione, non materiale girato


def blocchi(segs: list[dict], durate: dict[int, float]) -> list[dict]:
    """I tratti di girato che nessun segmento tocca, parte per parte.

    Il complemento degli intervalli **uniti**, non degli intervalli come stanno nel file:
    dopo `estendi.py` due segmenti vicini si sovrappongono, e sottraendoli uno per uno si
    aprirebbero buchi che non esistono.
    """
    out = []
    for p in SCARTABILI:
        usati = sorted((s["girato_start"], s["girato_end"]) for s in segs if s["parte"] == p)
        fine, vuoti = 0.0, []
        for a, b in usati:
            if a > fine:
                vuoti.append((fine, a))
            fine = max(fine, b)
        if fine < durate[p]:
            vuoti.append((fine, durate[p]))
        out += [{"parte": p, "start": a, "end": b, "durata": b - a}
                for a, b in vuoti if b - a >= MIN_BLOCCO]
    return out


def istanti(bl: dict) -> list[float]:
    """Quando campionare, dentro un blocco: mai sui bordi, dove il taglio è a cavallo."""
    n = min(max(round(bl["durata"] / OGNI), 1), MAX_MINI)
    passo = bl["durata"] / (n + 1)
    return [bl["start"] + passo * (k + 1) for k in range(n)]


def ore(s: float) -> str:
    """«12 ore e 33», non «12:32:56»: in una frase il timecode non si legge."""
    return f"{int(s // 3600)} ore e {int(s % 3600 // 60):02d}"


def num(x: float, d: int = 1) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def nome_mini(parte: int, t: float) -> str:
    return f"{parte}-{int(round(t)):06d}.jpg"


def estrai(bl: list[dict]) -> None:
    MINI.mkdir(exist_ok=True)
    manca = [(b["parte"], t) for b in bl for t in istanti(b)
             if not (MINI / nome_mini(b["parte"], t)).exists()]
    for i, (parte, t) in enumerate(manca, 1):
        subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{t:.2f}",
             "-i", str(GIRATO / f"Fuori campo di Anna - {parte}.mp4"),
             "-frames:v", "1", "-vf", "scale=220:-1", "-y",
             str(MINI / nome_mini(parte, t))], check=True)
        if i % 40 == 0:
            print(f"  {i}/{len(manca)}", flush=True)
    print(f"miniature: {len(manca)} nuove, {len(list(MINI.glob('*.jpg')))} in tutto")


def pagina(bl: list[dict], durate: dict[int, float]) -> str:
    tot = sum(b["durata"] for b in bl)
    girato = sum(durate[p] for p in SCARTABILI)

    righe = []
    for p in SCARTABILI:
        scarto = sum(b["durata"] for b in bl if b["parte"] == p)
        tacche = "".join(
            f'<i class="bl" style="left:{b["start"]/durate[p]*100:.4f}%;'
            f'width:{max(b["durata"]/durate[p]*100, 0.15):.4f}%"'
            f' title="{hms(b["start"])}–{hms(b["end"])} · {b["durata"]/60:.0f} min"></i>'
            for b in bl if b["parte"] == p)
        righe.append(
            f'<div class="riga"><div class="et"><span class="nome">'
            f'<i class="pip" style="background:var(--p{p})"></i>{etichetta(p)}</span>'
            f'<span class="dur">{hms(durate[p])}</span></div>'
            f'<div class="pista">{tacche}</div>'
            f'<span class="quota">{scarto/durate[p]:.0%}</span></div>')

    schede = []
    for b in sorted(bl, key=lambda x: (x["parte"], x["start"])):
        strisc = "".join(
            f'<figure><img src="{b64(MINI / nome_mini(b["parte"], t))}" alt="" loading="lazy">'
            f'<figcaption>{hms(t)}</figcaption></figure>' for t in istanti(b)
            if (MINI / nome_mini(b["parte"], t)).exists())
        schede.append(
            f'<article class="blocco" data-p="{b["parte"]}" data-dur="{b["durata"]:.0f}">'
            f'<header><span class="quale" style="--c:var(--p{b["parte"]})">'
            f'{etichetta(b["parte"], True)}</span>'
            f'<span class="tc">{hms(b["start"])} → {hms(b["end"])}</span>'
            f'<b class="quanto">{b["durata"]/60:.0f} min</b></header>'
            f'<div class="strisc">{strisc}</div></article>')

    lunghi = sorted(bl, key=lambda x: -x["durata"])[0]
    return f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Il girato scartato · Anna</title>
{font_incorporati()}
<style>
{stile_comune()}
.pista {{ height:16px; }}
.bl {{ position:absolute; top:0; bottom:0; background:var(--manca-scena); }}
.blocco {{ padding:1.4rem 0; border-top:1px solid var(--linea); }}
.blocco.spenta {{ display:none; }}
.blocco header {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:.7rem;
  margin-bottom:.8rem; }}
.quale {{ font-family:var(--display); font-weight:600; font-size:.9rem; color:var(--c); }}
.tc, .quanto {{ font-family:var(--mono); font-size:.78rem; color:var(--tenue);
  font-variant-numeric:tabular-nums; }}
.quanto {{ margin-left:auto; color:var(--inchiostro); font-weight:500; }}
.strisc {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(min(150px,45vw),1fr));
  gap:.5rem; }}
.strisc figure {{ margin:0; }}
.strisc img {{ width:100%; display:block; background:var(--pista); }}
.strisc figcaption {{ font-family:var(--mono); font-size:.64rem; color:var(--tenue);
  padding-top:.3rem; letter-spacing:.02em; }}
.nota {{ color:var(--tenue); font-size:.92rem; max-width:60ch; margin:2.5rem 0 0;
  padding-top:1.2rem; border-top:1px solid var(--linea); }}
footer {{ margin-top:3.5rem; padding-top:1.4rem; border-top:2px solid var(--inchiostro);
  color:var(--tenue); font-size:.88rem; max-width:64ch; }}
</style></head><body>
<div class="foglio">
<header class="testata">
  <div class="occhiello">Grifi · Sarchielli, 1975 — quello che non è entrato</div>
  <h1>Il girato <em>scartato</em></h1>
  <p class="sommario">Delle {ore(girato)} di <i>Fuori campo</i> girate e trasmesse,
  <b>{num(tot/3600)} ore non compaiono nel film</b>. Questa pagina dice dove sono e mostra
  com'è fatto ciò che è stato lasciato fuori: una miniatura ogni due minuti di materiale.</p>
</header>

<div class="cifre">
  <div class="cifra"><b>{num(tot/3600)} h</b><span>di girato mai usato</span></div>
  <div class="cifra"><b>{tot/girato:.0%}</b><span>del girato</span></div>
  <div class="cifra"><b>{len(bl)}</b><span>blocchi da 30 s in su</span></div>
  <div class="cifra"><b>{lunghi["durata"]/60:.0f} min</b><span>il blocco più lungo</span></div>
</div>

<h2>Dove sta il non usato</h2>
<p class="guida">Una riga per parte del girato: le tacche sono i tratti che <b>non</b>
ricompaiono nel montato. È l'esatto negativo delle barre dell'altra pagina — lì si accende
quello che è entrato nel film, qui quello che è rimasto fuori.</p>
{"".join(righe)}

<div class="filtri">
  <button class="chip" aria-pressed="true" data-p="0">tutte</button>
  {"".join(f'<button class="chip" aria-pressed="false" data-p="{p}">{etichetta(p, True)}</button>'
           for p in SCARTABILI)}
  <button class="chip" id="lunghi" aria-pressed="false"
   title="i blocchi più lunghi per primi">i più lunghi in cima</button>
</div>

<div class="blocchi">{"".join(schede)}</div>
<p class="vuoto">Nessun blocco per questo filtro.</p>

<p class="nota">La <b>presentazione al festival</b> (FC1, {hms(durate[1])}) non è contata qui:
non è girato, è il dibattito dopo la proiezione, e comparirebbe come il blocco più lungo di
tutti falsando la cifra in testa. I blocchi sotto i trenta secondi sono esclusi: sono lo
stacco fra due riusi vicini, non materiale scartato.</p>

<footer>Il negativo di <i>Anna nel Fuori campo</i>: là il montato ritrovato nel girato, qui il
girato che il montaggio non ha preso. Lo stesso dato letto dall'altro verso, con gli stessi
limiti — i confini valgono ±1 s, quindi un blocco può cominciare o finire un secondo più in
là.{provenienza()}</footer>
</div>
<script>
const blocchi = [...document.querySelectorAll('.blocco')];
let parte = 0;
const applica = () => {{
  let n = 0;
  for (const b of blocchi) {{
    const ok = parte === 0 || +b.dataset.p === parte;
    b.classList.toggle('spenta', !ok);
    if (ok) n++;
  }}
  document.querySelector('.vuoto').style.display = n ? 'none' : 'block';
}};
document.querySelectorAll('.chip[data-p]').forEach(c => c.onclick = () => {{
  parte = +c.dataset.p;
  document.querySelectorAll('.chip[data-p]').forEach(o =>
    o.setAttribute('aria-pressed', o === c ? 'true' : 'false'));
  applica();
}});
// stessa trappola dell'altra pagina: la madre deve contenere **solo** ciò che si riordina
const lunghi = document.getElementById('lunghi');
lunghi.onclick = () => {{
  const su = lunghi.getAttribute('aria-pressed') !== 'true';
  lunghi.setAttribute('aria-pressed', su ? 'true' : 'false');
  const madre = document.querySelector('.blocchi');
  const chiave = b => su ? -(+b.dataset.dur) : blocchi.indexOf(b);
  [...blocchi].sort((a, b) => chiave(a) - chiave(b)).forEach(b => madre.appendChild(b));
}};
applica();
</script></body></html>"""


if __name__ == "__main__":
    segs = json.loads((QUI / "segmenti-video.json").read_text())
    durate = durate_girato()
    bl = blocchi(segs, durate)
    print(f"{len(bl)} blocchi · {sum(b['durata'] for b in bl)/3600:.1f} h di girato mai usato")
    if "--miniature" in sys.argv:
        estrai(bl)
    out = QUI / "Il girato scartato.html"
    html = pagina(bl, durate)
    controlla_js(html)          # uno script rotto spegne tutti i filtri, non solo l'ultimo
    out.write_text(html)
    print(f"{out.name}  {out.stat().st_size/1e6:.1f} MB")
