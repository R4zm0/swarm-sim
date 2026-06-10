# core/save_load.py
"""
Save / Load — sérialisation de l'état de mission en cours.

Structure des saves :
    data/saves/{scenario_name}/{nom}.json

    Le scenario_name est stocké dans les meta pour vérification au load.
    On ne peut charger que des saves du même scénario que la session courante.
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime


def saves_dir(scenario_name: str) -> Path:
    """Dossier de saves pour un scénario donné."""
    return Path("data/saves") / scenario_name


def save(world, scheduler, coverage, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    state = {
        "meta": {
            "tick":          scheduler.tick_count,
            "saved_at":      datetime.now().isoformat(),
            "scenario_name": path.parent.name,   # dossier = nom du scénario
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


def scan_saves(scenario_name: str) -> list[dict]:
    """Liste les saves disponibles pour un scénario donné."""
    d = saves_dir(scenario_name)
    d.mkdir(parents=True, exist_ok=True)
    saves = []
    for p in sorted(d.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with open(p) as f:
                data = json.load(f)
            saves.append({
                "path":     p,
                "name":     p.stem,
                "tick":     data["meta"]["tick"],
                "date":     data["meta"]["saved_at"][:16].replace("T", " "),
            })
        except Exception:
            pass
    return saves