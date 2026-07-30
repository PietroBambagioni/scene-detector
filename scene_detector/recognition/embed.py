from __future__ import annotations

import numpy as np

# DINOv2 con register token, Apache 2.0. **Non** DINOv3: licenza custom Meta, che pretende
# approvazione e dati personali — fuori dalla regola di licenze del progetto.
DINO_MODEL = "facebook/dinov2-with-registers-large"

# Ritaglio di figura, in multipli dell'altezza del bbox del volto. Una figura umana e' ~7,5
# teste e il bbox di SCRFD e' il volto, un po' meno di una testa: il box voluto eccede quasi
# sempre l'inquadratura e viene tagliato.
#
# Misurato su *Rogue One*: ne sopravvive il **31-41%** (mediana per cluster), perche' un volto
# rilevato a 82-112 px su 272 di altezza frame *e'* un primo piano — il corpo non c'e'. In
# pratica questi sono ritagli di **busto**, ed e' comunque cio' che serve: armatura, mantello e
# sagoma stanno li', e il volto stretto non li vede.
BODY_UP, BODY_DOWN, BODY_W = 0.5, 6.0, 3.0

# media ImageNet, la normalizzazione con cui DINOv2 e' stato addestrato
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
FILL = (124, 116, 104)   # MEAN in 0-255: dopo la standardizzazione e' zero, neutro per l'encoder


def body_crop(pil_rgb, bbox):
    """Ritaglio di figura attorno al bbox del volto, tagliato ai bordi dell'inquadratura."""
    x1, y1, x2, y2 = bbox
    h = y2 - y1
    cx = (x1 + x2) / 2
    box = (max(0, int(cx - BODY_W * h / 2)), max(0, int(y1 - BODY_UP * h)),
           min(pil_rgb.width, int(cx + BODY_W * h / 2)),
           min(pil_rgb.height, int(y2 + BODY_DOWN * h)))
    return pil_rgb.crop(box)


def letterbox(img, size=224, fill=FILL):
    """Quadrato `size`x`size` con le proporzioni intatte.

    Schiacciare un ritaglio di figura (1:2 abbondante) in un quadrato ne distrugge la sagoma,
    che e' meta' del segnale su un personaggio in armatura.
    """
    from PIL import Image

    w, h = img.size
    s = size / max(w, h)
    r = img.resize((max(1, int(w * s)), max(1, int(h * s))), Image.BICUBIC)
    out = Image.new("RGB", (size, size), fill)
    out.paste(r, ((size - r.width) // 2, (size - r.height) // 2))
    return out


class BodyEncoder:
    """DINOv2 sui ritagli di figura, in streaming. `add()` durante la rilevazione, `result()` dopo.

    Accumula un buffer di `batch` ritagli e lo consuma appena e' pieno: la memoria resta
    limitata al batch invece di tenere migliaia di immagini (8839 volti su *Rogue One* sarebbero
    ~2 GB di PIL). I frame sono gia' in mano al chiamante durante la rilevazione dei volti,
    quindi non costa nessuna estrazione ffmpeg in piu' — solo l'encoder.

    Import di `torch`/`transformers` e caricamento del modello differiti al primo flush: il
    modulo resta importabile senza l'extra `characters`.
    """

    def __init__(self, model=DINO_MODEL, batch=32, device="mps"):
        self.model_name, self.batch, self.device = model, batch, device
        self._net = None
        self._buf = []
        self._out = []

    def _load(self):
        import torch
        from transformers import AutoModel

        self._torch = torch
        if self.device == "mps" and not torch.backends.mps.is_available():
            self.device = "cpu"
        self._net = AutoModel.from_pretrained(self.model_name).eval().to(self.device)

    def _flush(self):
        if not self._buf:
            return
        if self._net is None:
            self._load()
        a = np.stack([
            ((np.asarray(letterbox(im), np.float32) / 255.0 - MEAN) / STD).transpose(2, 0, 1)
            for im in self._buf
        ])
        with self._torch.no_grad():
            px = self._torch.from_numpy(a).to(self.device)
            self._out.append(self._net(pixel_values=px).pooler_output.float().cpu().numpy())
        self._buf.clear()

    def add(self, pil_rgb, bbox):
        """Accumula il ritaglio di figura per questo volto, nell'ordine di chiamata."""
        self._buf.append(body_crop(pil_rgb, bbox))
        if len(self._buf) >= self.batch:
            self._flush()

    def result(self):
        """-> embedding L2-normalizzati [N, 1024], nell'ordine in cui sono stati aggiunti."""
        self._flush()
        if not self._out:
            return np.zeros((0, 1024), np.float32)
        e = np.vstack(self._out)
        return e / (np.linalg.norm(e, axis=1, keepdims=True) + 1e-9)
