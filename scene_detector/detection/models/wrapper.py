from __future__ import annotations

from pathlib import Path


class _WindowedPredictor:
    """Windowing ufficiale TransNetV2, condiviso dai due modelli.

    predict(frames: uint8[N,27,48,3]) -> float[N] (prob boundary per frame).
    Finestre da 100 frame, passo 50, si tengono le 50 predizioni centrali (25:75),
    con padding di 25 frame all'inizio e riempimento in coda (come l'inference TF).
    Le sottoclassi forniscono modello (`_build`), tensore d'ingresso (`_to_tensor`) e
    estrazione dei logit (`_logits`).
    """

    name = ""

    def __init__(self, weights, device=None):
        import torch

        self.torch = torch
        self.device = self._default_device(device)
        self.model = self._build(Path(weights))

    def _default_device(self, device):
        return device or ("mps" if self.torch.backends.mps.is_available() else "cpu")

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
            for w in tqdm(range(n_windows), unit="win",
                          desc=f"[{self.name}] inference ({self.device})", disable=not progress):
                window = padded[w * 50:w * 50 + 100]  # [100,27,48,3] uint8
                logits = self._logits(self.model(self._to_tensor(window)))
                preds.append(torch.sigmoid(logits)[0, 25:75, 0].cpu().numpy())

        return np.concatenate(preds)[:n]

    def _build(self, weights):
        raise NotImplementedError

    def _to_tensor(self, window):
        raise NotImplementedError

    def _logits(self, out):
        raise NotImplementedError


class TransNetV2Predictor(_WindowedPredictor):
    """TransNetV2 (PyTorch). Input modello: uint8 [1,100,27,48,3]; ritorna (logits, dict)."""

    name = "transnet"

    def _build(self, weights):
        from .transnetv2 import TransNetV2

        model = TransNetV2()
        model.load_state_dict(self.torch.load(str(weights), map_location="cpu", weights_only=True))
        return model.eval().to(self.device)

    def _to_tensor(self, window):
        import numpy as np
        return self.torch.from_numpy(window[np.newaxis]).to(self.device)

    def _logits(self, out):
        return out[0]


class AutoShotPredictor(_WindowedPredictor):
    """AutoShot (TransNetV2Supernet, NAS). Input modello: float [1,3,100,27,48]

    (channels-first, senza /255, come l'inference ufficiale AutoShot). Il modello ritorna
    (single, many); si usa `single`.
    """

    name = "autoshot"

    def _default_device(self, device):
        # AutoShot: ColorHistograms usa op intere (bit-shift/segment-sum) non supportate su MPS
        # e i sotto-moduli tengono un attributo `.device` fisso -> default CPU per robustezza.
        return device or "cpu"

    def _build(self, weights):
        from .autoshot.supernet import TransNetV2Supernet

        torch = self.torch
        ck = torch.load(str(weights), map_location="cpu", weights_only=True)
        state = ck["net"] if isinstance(ck, dict) and "net" in ck else ck
        model = TransNetV2Supernet().eval()
        model.load_state_dict(state)
        model.to(self.device)

        dev = torch.device(self.device)
        for mod in model.modules():
            if hasattr(mod, "device"):
                mod.device = dev
        return model

    def _to_tensor(self, window):
        return (self.torch.from_numpy(window)
                .permute(3, 0, 1, 2).unsqueeze(0).float().to(self.device))

    def _logits(self, out):
        return out[0] if isinstance(out, (tuple, list)) else out
