# core/scenario_loader.py
import json
import numpy as np
from pathlib import Path
from core.world import World
from environment.zone import PatrolZone
from systems.coverage import CoverageMap


def load(path: str | Path) -> tuple[World, PatrolZone, CoverageMap]:
    with open(path) as f:
        data = json.load(f)

    world    = World()
    zone     = PatrolZone.from_dict(data["zone"])
    coverage = CoverageMap.from_scenario(zone, data)
    spawn    = np.array(data.get("spawn", data["zone"]["vertices"][0]), dtype=float)

    n         = len(data["drones"])
    P         = zone.perimeter
    RESERVED  = {"type", "team"}

    for i, cfg in enumerate(data["drones"]):
        drone = world.add_drone(cfg["type"], position=spawn.copy(), team=cfg.get("team", 0))

        for field, value in cfg.items():
            if field in RESERVED:
                continue
            if isinstance(value, (int, float)) and field in world.components:
                world.components.set(field, drone.id, float(value))

        # patrol_progress initial : chaque drone a son propre slot sur le périmètre
        prog = i * P / n
        world.components.set("patrol_progress", drone.id, prog)

        # target initiale = légèrement en avance sur le progress initial
        lookahead = min(P / n * 0.4, 600.0)
        world.targets[i] = zone.point_at((prog + lookahead) % P)

    # Ennemis fixes
    for enemy in data.get("enemies", []):
        world.add_enemy(np.array(enemy["position"], dtype=float))

    return world, zone, coverage