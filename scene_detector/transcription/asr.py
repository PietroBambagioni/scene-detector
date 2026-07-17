from __future__ import annotations

from ..core.cpu import resolve_workers


def transcribe(video_path, model="large-v3-turbo", language=None, vad=True,
               device="cpu", compute_type="int8", cpu_threads=0, progress=True):
    """Trascrive i dialoghi con faster-whisper.

    Ritorna (segments, detected_language) con segments = list[{start, end, text}].
    VAD (silero) attivo di default: salta musica/silenzio -> meno allucinazioni + più veloce.
    `model` accetta un nome (tiny/base/small/medium/large-v3/large-v3-turbo) o un path.
    `cpu_threads`: thread CTranslate2 (0 = auto: tutti i core meno 2). La barra avanza sui secondi di audio.
    """
    from faster_whisper import WhisperModel
    from tqdm import tqdm

    threads = resolve_workers(cpu_threads)
    wm = WhisperModel(model, device=device, compute_type=compute_type, cpu_threads=threads)
    segments, info = wm.transcribe(str(video_path), language=language, vad_filter=vad)

    total = getattr(info, "duration", None)
    bar = tqdm(total=round(total, 1) if total else None, unit="s", unit_scale=True,
               desc=f"[asr] {model} ({threads}t)", disable=not progress)
    out, last = [], 0.0
    for seg in segments:
        text = seg.text.strip()
        if text:
            out.append({"start": seg.start, "end": seg.end, "text": text})
        if total:
            bar.update(max(0.0, seg.end - last))
            last = seg.end
    if total:
        bar.n = round(total, 1)
        bar.refresh()
    bar.close()
    return out, info.language
