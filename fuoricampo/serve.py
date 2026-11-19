"""Server locale per la pagina di lavoro — l'unico caso in cui serve un server.

Per guardare la pagina basta il doppio click. Questo serve a **pilotare il browser da
un'estensione**, che i `file://` non li apre.

`python -m http.server` qui non va: non implementa `Range`, quindi ogni salto a un minutaggio
fa ripartire il video da zero e sembra un bug della pagina (è nei gotcha del CLAUDE.md). E
deve reggere gli abort che il browser manda a ogni seek, altrimenti la console si riempie di
tracce e la riproduzione si inceppa.

    .venv/bin/python fuoricampo/serve.py [porta]
"""
from __future__ import annotations

import os
import re
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

QUI = Path(__file__).parent


class ConRange(SimpleHTTPRequestHandler):
    def send_head(self):
        intervallo = self.headers.get("Range")
        if not intervallo:
            return super().send_head()

        percorso = self.translate_path(self.path)      # i symlink li segue open()
        if os.path.isdir(percorso):
            return super().send_head()
        try:
            f = open(percorso, "rb")
        except OSError:
            self.send_error(404)
            return None

        totale = os.fstat(f.fileno()).st_size
        m = re.match(r"bytes=(\d*)-(\d*)", intervallo.strip())
        if not m:
            f.close()
            self.send_error(400, "Range malformato")
            return None
        inizio = int(m.group(1)) if m.group(1) else 0
        fine = int(m.group(2)) if m.group(2) else totale - 1
        fine = min(fine, totale - 1)
        if inizio > fine:
            f.close()
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{totale}")
            self.end_headers()
            return None

        f.seek(inizio)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(percorso))
        self.send_header("Content-Range", f"bytes {inizio}-{fine}/{totale}")
        self.send_header("Content-Length", str(fine - inizio + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        return _Pezzo(f, fine - inizio + 1)

    def copyfile(self, sorgente, uscita):
        # il browser abortisce a ogni seek: è normale, non un errore da stampare
        try:
            super().copyfile(sorgente, uscita)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, formato, *args):
        if "206" not in (args[1] if len(args) > 1 else ""):
            super().log_message(formato, *args)


class _Pezzo:
    """Wrapper che smette di leggere alla fine dell'intervallo richiesto."""

    def __init__(self, f, quanti):
        self.f, self.restano = f, quanti

    def read(self, n=-1):
        if self.restano <= 0:
            return b""
        dati = self.f.read(self.restano if n < 0 else min(n, self.restano))
        self.restano -= len(dati)
        return dati

    def close(self):
        self.f.close()


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8747
    # radice il sottoprogetto e non `lavoro/`: la pagina cerca le miniature in `../thumbs`,
    # che da `file://` sta un livello sopra e via HTTP sarebbe fuori dalla radice — 404 su
    # tutte e 346, senza che la pagina abbia niente che non va
    radice = QUI
    srv = ThreadingHTTPServer(("127.0.0.1", porta),
                              partial(ConRange, directory=str(radice)))
    srv.daemon_threads = True
    print(f"http://127.0.0.1:{porta}/lavoro/anna-lavoro.html  (radice: {radice})")
    srv.serve_forever()
