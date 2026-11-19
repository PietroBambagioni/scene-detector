"""Le correzioni fatte a mano nella pagina tornano dove devono stare.

Due destinazioni, perché sono due cose con vite diverse:

- la **descrizione** e la **trascrizione del parlato** appartengono al film e vanno in
  `clips/Anna/manifest.json`, dove le legge anche il catalogo, e sopravvivono a qualunque
  ritaratura delle soglie di questo sottoprogetto;
- il **verdetto** sull'aggancio appartiene a *questo* run del matching e resta in
  `verdetti.json`, qui accanto.

Mescolarle sembra comodo e costa una delle due alla prima ritaratura.

    .venv/bin/python fuoricampo/applica_correzioni.py correzioni.json
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from timeline import MANIFEST, QUI

VERDETTI = QUI / "verdetti.json"


def applica(correzioni: list[dict], shots: list[dict]) -> tuple[int, list[dict]]:
    """Scrive le descrizioni sugli shot, accoppiando per `start_frame`.

    **Mai per indice.** Basta un run a soglia diversa perché il numero di shot cambi e gli
    indici scivolino tutti di uno: le correzioni finirebbero su shot che non descrivono, in
    silenzio. Se lo `start_frame` non c'è più, la correzione non si applica e torna indietro
    fra le orfane — un campo assegnato male è peggio di uno perso.
    """
    per_frame = {sh["start_frame"]: sh for sh in shots}
    campi = {"descrizione": "description", "dialogo": "dialogue"}
    scritte, orfane = 0, []
    for c in correzioni:
        tocca = [k for k in campi if k in c]
        if not tocca:
            continue
        sh = per_frame.get(c["start_frame"])
        if sh is None:
            orfane.append(c)
            continue
        for k in tocca:
            sh[campi[k]] = c[k]
        scritte += 1
    return scritte, orfane


def unisci_verdetti(correzioni: list[dict], vecchi: dict, quando: str,
                    esistenti: set[int]) -> dict:
    """I verdetti si accumulano fra sessioni: l'ultimo su uno stesso shot vince.

    Vale la stessa regola delle descrizioni: un verdetto su uno `start_frame` che nel manifest
    non c'è più non si salva. Sarebbe spazzatura che si accumula e che poi falsa il conteggio
    della precisione, cioè l'unica cosa per cui i verdetti esistono.
    """
    for c in correzioni:
        if "verdetto" not in c or c["start_frame"] not in esistenti:
            continue
        vecchi[str(c["start_frame"])] = {
            "shot": c.get("shot"), "verdetto": c["verdetto"], "quando": quando,
            **({"nota": c["nota"]} if c.get("nota") else {}),
        }
    return vecchi


def demo():
    shots = [{"start_frame": 100, "description": "vecchia"},
             {"start_frame": 250, "description": "altra"}]
    corr = [{"start_frame": 100, "descrizione": "nuova", "dialogo": "parlato corretto",
             "verdetto": "giusto", "shot": 0},
            {"start_frame": 999, "descrizione": "orfana", "shot": 7}]
    scritte, orfane = applica(corr, shots)
    assert scritte == 1 and len(orfane) == 1, (scritte, orfane)
    assert shots[0]["description"] == "nuova"
    assert shots[0]["dialogue"] == "parlato corretto"
    assert shots[1]["description"] == "altra", "toccato uno shot che non andava toccato"
    esistenti = {sh["start_frame"] for sh in shots}
    v = unisci_verdetti(corr, {}, "ora", esistenti)
    assert v["100"]["verdetto"] == "giusto", v
    assert "999" not in v, "verdetto salvato su uno shot che non esiste"
    # l'indice non deve entrare in gioco: stessi shot, indici slittati, stesso risultato
    slittati = [{"start_frame": 100, "description": "x"}] * 1 + shots[1:]
    assert applica([{"start_frame": 100, "descrizione": "z"}], slittati)[0] == 1
    print("ok")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--demo"]:
        demo()
        raise SystemExit

    if len(sys.argv) < 2:
        raise SystemExit("uso: applica_correzioni.py correzioni.json")
    dati = json.loads(Path(sys.argv[1]).read_text())
    correzioni = dati["correzioni"]

    man = json.loads(MANIFEST.read_text())
    esistenti = {sh["start_frame"] for sh in man["shots"]}
    scritte, orfane = applica(correzioni, man["shots"])
    orfane += [c for c in correzioni
               if not ({"descrizione", "dialogo"} & set(c)) and c["start_frame"] not in esistenti]

    if scritte:
        backup = MANIFEST.with_suffix(".pre-correzioni.bak.json")
        if not backup.exists():          # il primo stato buono non si sovrascrive mai
            shutil.copy2(MANIFEST, backup)
        MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1))

    quando = dati.get("generato", datetime.now().isoformat(timespec="seconds"))
    vecchi = json.loads(VERDETTI.read_text()) if VERDETTI.exists() else {}
    prima = len(vecchi)
    nuovi = unisci_verdetti(correzioni, vecchi, quando, esistenti)
    VERDETTI.write_text(json.dumps(nuovi, ensure_ascii=False, indent=1))

    print(f"shot corretti nel manifest (descrizione e/o parlato): {scritte}")
    print(f"verdetti: {len(nuovi)} in tutto ({len(nuovi)-prima} nuovi) -> {VERDETTI.name}")
    conteggio = {}
    for v in nuovi.values():
        conteggio[v["verdetto"]] = conteggio.get(v["verdetto"], 0) + 1
    if conteggio:
        print("  " + " · ".join(f"{k}: {n}" for k, n in sorted(conteggio.items())))
    if orfane:
        print(f"\n⚠ {len(orfane)} correzioni NON applicate: lo start_frame non esiste più nel "
              f"manifest (i confini si sono spostati). Non sono state messe altrove.")
        for c in orfane[:10]:
            print(f"    start_frame {c['start_frame']} (era shot {c.get('shot','?')})")
    if scritte:
        print("\nRigenera con: .venv/bin/python fuoricampo/lavoro.py")
