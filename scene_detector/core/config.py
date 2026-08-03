from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class DetectorKind(str, Enum):
    transnet = "transnet"
    autoshot = "autoshot"
    pyscenedetect = "pyscenedetect"


class SplitMode(str, Enum):
    copy = "copy"          # veloce, snap a keyframe
    reencode = "reencode"  # frame-accurate, lento
    none = "none"          # non taglia: la UI riproduce il film intero con media fragments


@dataclass
class Config:
    video: Path
    output_dir: Path = Path("clips")
    detector: DetectorKind = DetectorKind.transnet
    split_mode: SplitMode = SplitMode.copy
    # Soglia boundary neurale. 0,05 e non 0,5: con `runs_to_ranges` una corsa di frame caldi è
    # una transizione sola, quindi la soglia bassa non moltiplica i tagli — recupera le
    # dissolvenze. Misurato su 1634 transizioni reali (ClipShots): recall 0,088 → 0,325, e sui
    # soli stacchi netti 0,81 → 0,95. Costo: +35% di shot su un film.
    threshold: float = 0.05
    # Frame minimi per scena. 5 e non 15, ma **solo** perché la soglia è scesa a 0,05: a soglia
    # alta i due valori sono equivalenti (misurato in §5.7: +1 punto di F1), a soglia bassa
    # nascono più shot brevi legittimi e la fusione cieca ne mangia di veri — sui soli stacchi
    # netti 0,77 con 15 contro 0,93 con 5. Le due tarature non sono separabili.
    min_scene_len: int = 5
    agreement_tol: int = 5        # tolleranza (frame) per agreement in ensemble
    transnet_weights: Path | None = None
    autoshot_weights: Path | None = None
    # Confini presi da un manifest corretto a mano nella UI invece che dal detector. Il detector
    # non gira e `min_scene_len` non si applica: se hai tagliato uno shot di 3 frame, l'hai
    # voluto tu. Da qui in poi la pipeline non sa la differenza — split, miniature e UI
    # ripartono dai confini nuovi.
    from_manifest: Path | None = None
    # trascrizione dialoghi (ASR)
    asr: bool = False
    asr_model: str = "large-v3-turbo"
    asr_lang: str | None = None
    asr_threads: int = 0
    # diarizzazione: chi parla in ogni shot (binario esterno `speech`, non una dep Python).
    # Indipendente da `asr`: dice *chi* parla e quando, non cosa dice. Opt-in come `scenes` —
    # `--all` non la include finché il linking speaker↔volto non è misurato.
    diarize: bool = False
    # descrizione visiva per shot (VLM)
    vlm: bool = False
    vlm_model: str = "mlx-community/Qwen3-VL-8B-Instruct-4bit"
    vlm_frames: int = 3
    # riconoscimento personaggi (faces)
    faces: bool = False
    faces_gallery: Path | None = None
    faces_frames: int = 6
    faces_threshold: float = 0.5
    faces_min_score: float = 0.5
    faces_min_px: int = 50        # lato minimo del bbox: sotto, l'embedding e' rumore
    faces_min_shots: int = 3      # un personaggio del cast ricorre in >=N shot distinti (non volti)
    # Rimette in discussione i cluster che ArcFace non riconosce come volti umani (droidi,
    # elmetti) sui ritagli di figura, con una testa lineare adattata al film. Costa il
    # caricamento di DINOv2 e ~26 img/s in piu' sullo stesso passaggio di frame — nessuna
    # estrazione aggiuntiva. Vedi `recognition/adapt.py` per da dove viene la supervisione.
    faces_refine: bool = False
    # Soglia coseno del raffinamento. **Separata da `faces_threshold` e non per pignoleria**:
    # quella è tarata su ArcFace, questa vive nello spazio DINOv2 adattato, e le due
    # distribuzioni di similarità non sono commensurabili. Riusare 0,50 qui lascia i sospetti in
    # un gruppo solo — misurato su *Rogue One* con verità annotata (`prove/labels-661.txt`,
    # 36 Vader + 35 stormtrooper + 13 altro):
    #
    #   t=0,50 → purezza 0,43, un gruppo, Vader e trooper **non** separati
    #   t=0,70 → purezza 0,98, cinque gruppi, separati
    #   t=0,80 → purezza 0,92
    faces_refine_threshold: float = 0.70
    # raggruppamento shot -> scene (Optimal Sequential Grouping, solo visivo)
    scenes: bool = False
    # None: stimato dal gomito dei valori singolari — ma la stima **sottostima di ~40%** (media
    # 7,2 contro 12,6 reali su RAI) e non segue il video. In pratica va passato.
    n_scenes: int | None = None
    # taglio clip
    jobs: int = 0                 # processi ffmpeg paralleli (0 = auto)
