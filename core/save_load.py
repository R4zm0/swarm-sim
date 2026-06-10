# core/save_load.py




"""
Save / Load — sérialisation de l'état de mission en cours.

Design :
    Config immuable (speed, mass, sensor_radius...) NON sauvegardée.
    Elle est rechargée depuis le scénario JSON au load.

    Seul l'état de mission est persisté :
        - Composants mutables (battery_level, mode, jamming_level...)
        - Positions, velocities, targets
        - alive_mask
        - Tick courant
        - Coverage map (valeurs de couverture)

Workflow :
    save(world, scheduler, coverage, path)
        → data/saves/nom.json

    load_state(world, scheduler, coverage, path)
        → restaure l'état  (world déjà initialisé depuis le scénario JSON)
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime


def save(world, scheduler, coverage, path: str | Path) -> None:
    """Sauvegarde l'état courant de la mission dans un fichier JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    state = {
        "meta": {
            "tick":     scheduler.tick_count,
            "saved_at": datetime.now().isoformat(),
        },
        "world": {
            "components": world.components.state_dict(),
            "positions":  world.positions.tolist(),
            "velocities": world.velocities.tolist(),
            "targets":    world.targets.tolist(),
            "alive_mask": world.alive_mask.tolist(),
        },
        "coverage": coverage.state_dict() if coverage is not None else None,
    }

    with open(path, "w") as f:
        json.dump(state, f, indent=2)

    print(f"[save] tick {scheduler.tick_count} → {path}")


def load_state(world, scheduler, coverage, path: str | Path) -> None:
    """
    Restaure un état de mission sauvegardé.

    Pré-requis : le world doit déjà être initialisé depuis le scénario JSON
    (les drones doivent exister — leurs configs immuables sont rechargées depuis JSON).
    """
    path = Path(path)
    if not path.exists():
        print(f"[load] fichier introuvable : {path}")
        return

    with open(path) as f:
        state = json.load(f)

    w = state["world"]

    scheduler.tick_count = state["meta"]["tick"]

    world.components.load_state(w["components"])
    world.positions  = np.array(w["positions"],  dtype=float)
    world.velocities = np.array(w["velocities"], dtype=float)
    world.targets    = np.array(w["targets"],    dtype=float)
    world.alive_mask = np.array(w["alive_mask"], dtype=bool)

    if coverage is not None and state.get("coverage") is not None:
        coverage.load_state(state["coverage"])

    print(f"[load] tick {scheduler.tick_count} ← {path}")