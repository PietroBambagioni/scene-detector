from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

log = logging.getLogger("scene_detector")


# ------------------------------------------------------------- ambiente -----

def _pkg_version(name):
    try:
        from importlib.metadata import version
        return version(name)
    except Exception:
        return None


def _ffmpeg_version():
    try:
        out = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout
        return out.splitlines()[0].split(" ")[2] if out else None
    except Exception:
        return None


def collect_env() -> dict:
    """Versioni di python + tool/pacchetti rilevanti al run (per riproducibilità)."""
    env = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "ffmpeg": _ffmpeg_version(),
        "numpy": _pkg_version("numpy"),
        "scenedetect": _pkg_version("scenedetect"),
        "faster_whisper": _pkg_version("faster-whisper"),
        "mlx_vlm": _pkg_version("mlx-vlm"),
        "insightface": _pkg_version("insightface"),
        "onnxruntime": _pkg_version("onnxruntime"),
        "psutil": _pkg_version("psutil"),
    }
    try:
        import torch
        env["torch"] = torch.__version__
        env["mps_available"] = bool(torch.backends.mps.is_available())
    except Exception:
        env["torch"] = None
        env["mps_available"] = None
    return env


def command_snapshot() -> dict:
    """Come è stato lanciato il run: argv completo, host, cwd, timestamp."""
    return {
        "argv": sys.argv,
        "started": datetime.now().astimezone().isoformat(timespec="seconds"),
        "host": socket.gethostname(),
        "cwd": os.getcwd(),
    }


# --------------------------------------------------------- campionamento ----

class ResourceSampler:
    """Thread di background: campiona ~ogni `interval`s CPU% e RSS del processo (+figli
    ffmpeg/torch), tenendo media e picco. No-op se psutil non è installato."""

    def __init__(self, interval: float = 0.5):
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.cpu_samples: list[float] = []
        self.rss_peak = 0
        try:
            import psutil
            self._proc = psutil.Process()
        except Exception:
            self._proc = None

    def _run(self):
        p = self._proc
        p.cpu_percent(None)  # prima chiamata: azzera il riferimento
        while not self._stop.wait(self.interval):
            try:
                cpu = p.cpu_percent(None)
                rss = p.memory_info().rss
                for c in p.children(recursive=True):
                    try:
                        cpu += c.cpu_percent(None)
                        rss += c.memory_info().rss
                    except Exception:
                        pass
                self.cpu_samples.append(cpu)
                self.rss_peak = max(self.rss_peak, rss)
            except Exception:
                break

    def start(self):
        if self._proc is None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=2)

    def summary(self) -> dict:
        if not self.cpu_samples:
            return {"cpu_pct_avg": None, "cpu_pct_peak": None, "rss_peak_mb": None}
        return {
            "cpu_pct_avg": round(sum(self.cpu_samples) / len(self.cpu_samples), 1),
            "cpu_pct_peak": round(max(self.cpu_samples), 1),
            "rss_peak_mb": round(self.rss_peak / 1e6, 1),
        }


# ----------------------------------------------------------------- disco ----

def _dir_size(path) -> int:
    p = Path(path)
    if not p.exists():
        return 0
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


# ----------------------------------------------------------- telemetria -----

class Telemetry:
    """Osservabilità di un run: cartella `logs/run-<ts>/` con log umano, snapshot config
    e metriche per step (tempo, CPU%, RSS, disco) + esiti."""

    def __init__(self, out_dir):
        self.out_dir = Path(out_dir)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_dir = self.out_dir / "logs" / f"run-{ts}"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._link_latest()
        self._setup_logging()
        self.steps: list[dict] = []
        self._t0 = time.perf_counter()
        self._started = datetime.now().astimezone().isoformat(timespec="seconds")

    def _link_latest(self):
        link = self.log_dir.parent / "latest"
        try:
            if link.is_symlink() or link.exists():
                link.unlink()
            link.symlink_to(self.log_dir.name)
        except OSError:
            pass  # FS senza symlink: la cartella timestampata basta

    def _setup_logging(self):
        log.setLevel(logging.INFO)
        for h in list(log.handlers):
            log.removeHandler(h)
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
        fh = logging.FileHandler(self.log_dir / "run.log", encoding="utf-8")
        fh.setFormatter(fmt)
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        log.addHandler(fh)
        log.addHandler(ch)
        log.propagate = False

    def write_config(self, payload: dict):
        """Snapshot della config all'avvio (persiste anche se il run crasha subito dopo)."""
        (self.log_dir / "config.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )

    def _disk(self) -> dict:
        return {
            "output_mb": round(_dir_size(self.out_dir) / 1e6, 1),
            "free_gb": round(shutil.disk_usage(self.out_dir).free / 1e9, 1),
        }

    @contextmanager
    def step(self, name: str):
        """Avvolge una fase: logga inizio/fine, misura tempo + risorse + disco, accumula.

        Yield un dict `outcome` che il chiamante riempie con gli esiti (n_shots, ecc.).
        Il record è persistito a fine step (un run interrotto conserva gli step conclusi)."""
        log.info("▶ %s", name)
        sampler = ResourceSampler()
        sampler.start()
        t = time.perf_counter()
        outcome: dict = {}
        try:
            yield outcome
        finally:
            elapsed = time.perf_counter() - t
            sampler.stop()
            res = sampler.summary()
            record = {
                "step": name,
                "elapsed_s": round(elapsed, 2),
                **res,
                "disk": self._disk(),
                "outcome": outcome,
            }
            self.steps.append(record)
            self._flush()
            cpu = f"cpu~{res['cpu_pct_avg']}%/{res['cpu_pct_peak']}%" if res["cpu_pct_avg"] is not None else "cpu n/a"
            rss = f"rss~{res['rss_peak_mb']}MB" if res["rss_peak_mb"] is not None else ""
            log.info("✔ %s — %.1fs | %s %s", name, elapsed, cpu, rss)

    def _flush(self):
        payload = {
            "started": self._started,
            "wall_clock_s": round(time.perf_counter() - self._t0, 2),
            "steps": self.steps,
        }
        (self.log_dir / "run_stats.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def close(self):
        self._flush()
        log.info("run completato in %.1fs — log in %s", time.perf_counter() - self._t0, self.log_dir)
