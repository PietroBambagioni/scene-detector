from __future__ import annotations

from pathlib import Path


class TransNetV2Predictor:
    """Carica TransNetV2 (PyTorch) e applica il windowing ufficiale.

    predict(frames: uint8[N,27,48,3]) -> float[N] (prob boundary per frame).
    Finestre da 100 frame, passo 50, si tengono le 50 predizioni centrali (25:75),
    con padding di 25 frame all'inizio e riempimento in coda (come l'inference TF).
    """

    def __init__(self, weights, device=None):
        import torch
        from .transnetv2 import TransNetV2

        self.torch = torch
        if device is None:
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.device = device

        self.model = TransNetV2()
        self.model.load_state_dict(torch.load(str(Path(weights)), map_location="cpu"))
        self.model.eval().to(self.device)

    def predict(self, frames, progress=True):
        import numpy as np
        from tqdm import tqdm

        torch = self.torch
        n = len(frames)
        pad_end = 25 + 50 - (n % 50 if n % 50 != 0 else 50)
        padded = np.concatenate(
            [np.repeat(frames[:1], 25, axis=0), frames, np.repeat(frames[-1:], pad_end, axis=0)],
            axis=0,
        )

        n_windows = (len(padded) - 100) // 50 + 1
        preds = []
        with torch.no_grad():
            for w in tqdm(range(n_windows), unit="win", desc=f"[transnet] inference ({self.device})",
                          disable=not progress):
                window = padded[w * 50:w * 50 + 100][np.newaxis]  # [1,100,27,48,3] uint8
                t = torch.from_numpy(window).to(self.device)
                logits, _ = self.model(t)
                preds.append(torch.sigmoid(logits)[0, 25:75, 0].cpu().numpy())

        return np.concatenate(preds)[:n]


class AutoShotPredictor:
    """Carica AutoShot (TransNetV2Supernet, NAS) e applica il windowing.

    predict(frames: uint8[N,27,48,3]) -> float[N]. Input modello: float [1,3,100,27,48]
    (channels-first, senza /255, come l'inference ufficiale AutoShot). Il modello ritorna
    (single, many); si usa `single`.
    """

    def __init__(self, weights, device=None):
        import torch
        from .autoshot.supernet import TransNetV2Supernet

        self.torch = torch
        # AutoShot: ColorHistograms usa op intere (bit-shift/segment-sum) non supportate su MPS
        # e i sotto-moduli tengono un attributo `.device` fisso -> default CPU per robustezza.
        self.device = device or "cpu"

        ck = torch.load(str(Path(weights)), map_location="cpu", weights_only=True)
        state = ck["net"] if isinstance(ck, dict) and "net" in ck else ck
        self.model = TransNetV2Supernet().eval()
        self.model.load_state_dict(state)
        self.model.to(self.device)

        dev = torch.device(self.device)
        for mod in self.model.modules():
            if hasattr(mod, "device"):
                mod.device = dev

    def predict(self, frames, progress=True):
        import numpy as np
        from tqdm import tqdm

        torch = self.torch
        n = len(frames)
        pad_end = 25 + 50 - (n % 50 if n % 50 != 0 else 50)
        padded = np.concatenate(
            [np.repeat(frames[:1], 25, axis=0), frames, np.repeat(frames[-1:], pad_end, axis=0)],
            axis=0,
        )

        n_windows = (len(padded) - 100) // 50 + 1
        preds = []
        with torch.no_grad():
            for w in tqdm(range(n_windows), unit="win", desc=f"[autoshot] inference ({self.device})",
                          disable=not progress):
                window = padded[w * 50:w * 50 + 100]  # [100,27,48,3] uint8
                x = torch.from_numpy(window).permute(3, 0, 1, 2).unsqueeze(0).float().to(self.device)
                out = self.model(x)
                single = out[0] if isinstance(out, (tuple, list)) else out
                preds.append(torch.sigmoid(single)[0, 25:75, 0].cpu().numpy())

        return np.concatenate(preds)[:n]
