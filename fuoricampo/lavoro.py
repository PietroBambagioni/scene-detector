"""La pagina da lavoro: la stessa timeline, ma coi due filmati dentro.

I sette video stanno in due posti diversi del disco e una pagina `file://` carica senza
storie solo ciò che le sta sotto. Non si copiano 30 GB: qui si creano sette **symlink** e la
pagina li referenzia per path relativo — lo stesso schema di `clips/Film/`. Questo è l'unico
file dove compaiono i path assoluti del materiale: se i video si spostano, si rilancia solo
questo.

La pagina che ne esce **non è condivisibile** ed è giusto così: senza i video accanto mostra
schermi neri. Per mandarla in giro c'è `artifact.py --offline`.

    .venv/bin/python fuoricampo/lavoro.py
"""
from __future__ import annotations

from pathlib import Path

from artifact import controlla_js, costruisci, dati
from impronta import PARTI
from timeline import GIRATO, QUI, RADICE

DOVE = QUI / "lavoro"
FILM = RADICE / "Film" / "Anna.mp4"


def collega() -> list[str]:
    """Un symlink per video, rifatto se rotto o se punta altrove. Ritorna cosa manca."""
    video = DOVE / "ANNA"
    video.mkdir(parents=True, exist_ok=True)
    coppie = [("Anna.mp4", FILM)] + [
        (f"Fuori campo di Anna - {i}.mp4", GIRATO / f"Fuori campo di Anna - {i}.mp4")
        for i in PARTI]
    mancanti = []
    for nome, sorgente in coppie:
        link = video / nome
        if not sorgente.exists():
            mancanti.append(str(sorgente))
            continue
        # `exists()` su un symlink rotto è False: va tolto guardando il link, non il bersaglio
        if link.is_symlink() or link.exists():
            if link.is_symlink() and link.readlink() == sorgente:
                continue
            link.unlink()
        link.symlink_to(sorgente)
    return mancanti


if __name__ == "__main__":
    mancanti = collega()
    righe, segs, man, durate = dati()
    out = DOVE / "anna-lavoro.html"
    pagina = costruisci(righe, segs, man["duration"], durate, "lavoro")
    controlla_js(pagina)      # uno script solo: se è rotto, non funziona più niente
    out.write_text(pagina)
    print(f"{out}  {out.stat().st_size/1e6:.2f} MB")
    for m in mancanti:
        print(f"  ⚠ video mancante, il confronto non partirà: {m}")
    print("Aprilo col doppio click (mai con python -m http.server: senza Range i salti "
          "fanno ripartire il video da zero).")
