from __future__ import annotations

import os

RESERVED_CORES = 2  # core lasciati liberi in modalità auto (sistema reattivo)


def resolve_workers(requested: int, reserve: int = RESERVED_CORES) -> int:
    """Numero di worker CPU da usare.

    - `requested > 0`: valore esplicito, usato così com'è.
    - `requested == 0` (auto): tutti i core meno `reserve` (min 1), per non
      saturare la macchina e mantenerla usabile durante il job.
    """
    if requested and requested > 0:
        return requested
    total = os.cpu_count() or 4
    return max(1, total - reserve)
