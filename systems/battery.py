# systems/battery.py
"""
Drain de batterie + passage en mode DEAD quand la batterie est vide.
"""

import numpy as np
from core.world import World
from entities.types import DroneMode

DEAD_THRESHOLD = 0.01   # niveau en-dessous duquel le drone est considéré HS


def update(world: World, raw_steering: np.ndarray, dt: float) -> None:
    """
    raw_steering : (N, 2) — force avant division par la masse.
    Drain normalisé par max_force → power_idle et power_max_steer sont en %capacité/s.

    Effet de bord : les drones dont la batterie passe sous DEAD_THRESHOLD
    sont automatiquement marqués DEAD → exclus du tick suivant via alive_mask.
    """
    mask = world.alive_mask

    thrust_ratio = (
        np.linalg.norm(raw_steering[mask], axis=1)
        / world.max_forces[mask]
    )

    drain = (world.power_idle[mask] + world.power_max_steer[mask] * thrust_ratio) * dt

    levels = world.battery_levels
    levels[mask] -= drain
    levels[:]     = np.clip(levels, 0.0, 1.0)

    # Passe en DEAD les drones sans batterie — exclus du prochain TickContext
    for drone_id in np.where(mask)[0]:
        if levels[drone_id] < DEAD_THRESHOLD:
            world.components.set("mode", drone_id, DroneMode.DEAD)