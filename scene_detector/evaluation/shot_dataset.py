"""Ground truth pubblico per la valutazione: il test set di SHOT (AutoShot, CVPR-W 2023).

Annotare a mano ~20 boundary misura solo la *precision*: verifichi quelli che il detector ha
sparato, non vedi quelli che ha mancato. Il test set di SHOT risolve entrambi i problemi —
200 video annotati per intero, 2716 shot, **2516 boundary di cui 438 (17%) transizioni graduali
col loro range**, che è ciò che serve a `transition_iou` per non essere inerte.

Tutto arriva dal mirror HuggingFace da cui prendiamo già `autoshot.pth`: niente Baidu, niente
Google Drive, niente auth. Gli archivi video sono ~20 GB in totale, ma non si scaricano interi:
si legge l'indice dello zip remoto via range HTTP e si estraggono **solo** i video del test set.

Licenza: AutoShot è MIT. Il mirror HF non dichiara licenza — lo usiamo per scaricare in locale,
non ridistribuiamo nulla.
"""
from __future__ import annotations

import io
import pickle
import re
import urllib.request
from pathlib import Path

BASE = "https://huggingface.co/backseollgi/AutoShot/resolve/main"
GT_FILE = "gt_scenes_dict_baseline_v2.pickle"
# i 200 video di test sono sparsi fra questi archivi (non c'è uno zip "test")
VIDEO_ZIPS = ["video_download.zip", "original_videos.zip", "ads_game_videos.zip",
              "ads_game_videos_2.zip", "video_download_2.zip", "video_download_3.zip",
              "video_download_4.zip", "video_download_5.zip"]


# ------------------------------------------------------------- ground truth ---

class _SafeUnpickler(pickle.Unpickler):
    """Unpickler che accetta solo la ricostruzione di array numpy.

    Un pickle è codice eseguibile e questo arriva da un mirror di terze parti: caricarlo con
    `pickle.load` sarebbe esecuzione arbitraria. Gli opcode di questo file importano soltanto
    i tre simboli qui sotto — verificato con `pickletools` — e qualunque altro simbolo alza.
    """

    ALLOWED = {("numpy.core.multiarray", "_reconstruct"), ("numpy", "ndarray"), ("numpy", "dtype")}

    def find_class(self, module, name):
        if (module, name) not in self.ALLOWED:
            raise pickle.UnpicklingError(f"simbolo non consentito nel pickle: {module}.{name}")
        return super().find_class(module, name)


def load_ground_truth(path):
    """-> {video_id: [(start, end), …]} con gli shot inclusivi, il formato di `evaluate`."""
    with open(path, "rb") as f:
        raw = _SafeUnpickler(f).load()
    return {str(k): [tuple(int(x) for x in row) for row in v] for k, v in raw.items()}


def fetch_ground_truth(dest_dir):
    """Scarica il pickle del ground truth (53 KB) e lo carica. -> dict come `load_ground_truth`."""
    dest = Path(dest_dir) / GT_FILE
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(f"{BASE}/{GT_FILE}", dest)
    return load_ground_truth(dest)


# ------------------------------------------------------- zip remoto a range ---

class _HttpFile(io.RawIOBase):
    """File-like su HTTP con range: `zipfile` ci si appoggia e scarica solo ciò che legge."""

    def __init__(self, url):
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD")) as r:
            self.size = int(r.headers["Content-Length"])
            self.url = r.url                       # dopo il redirect al CDN
        self.pos = 0

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def tell(self):
        return self.pos

    def readable(self):
        return True

    def seekable(self):
        return True

    def read(self, n=-1):
        n = self.size - self.pos if n < 0 else min(n, self.size - self.pos)
        if n <= 0:
            return b""
        req = urllib.request.Request(self.url,
                                     headers={"Range": f"bytes={self.pos}-{self.pos + n - 1}"})
        with urllib.request.urlopen(req) as r:
            data = r.read()
        self.pos += len(data)
        return data

    def readinto(self, b):
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


def _open_remote_zip(url):
    import zipfile
    return zipfile.ZipFile(io.BufferedReader(_HttpFile(url), buffer_size=1 << 16))


def fetch_videos(gt, dest_dir, limit=None, on_progress=None):
    """Estrae dai zip remoti i video presenti in `gt`, saltando quelli già su disco.

    Scorre gli archivi finché non ha `limit` video (None = tutti i 200). Ritorna
    {video_id: Path}. I ~200 video pesano ~4 GB: con `limit=50` si sta sotto il giga e si hanno
    comunque ~700 boundary, abbastanza per un numero solido.
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    found = {p.stem: p for p in dest.glob("*.mp4") if p.stem in gt}

    for zip_name in VIDEO_ZIPS:
        if limit is not None and len(found) >= limit:
            break
        zf = _open_remote_zip(f"{BASE}/{zip_name}")
        for name in zf.namelist():
            if limit is not None and len(found) >= limit:
                break
            stem = re.sub(r"\.[^.]+$", "", name.split("/")[-1])
            if name.startswith("__MACOSX") or stem not in gt or stem in found:
                continue
            out = dest / f"{stem}.mp4"
            with zf.open(name) as src, open(out, "wb") as f:            # solo questa voce
                while chunk := src.read(1 << 20):
                    f.write(chunk)
            found[stem] = out
            if on_progress:
                on_progress(stem, len(found), limit)
        zf.close()
    return found
