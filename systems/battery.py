# systems/battery.py
import numpy as np
from core.world import World


def update(world: World, raw_steering: np.ndarray, dt: float) -> None:
    """
    raw_steering : (N, 2) — force avant division par la masse (retourné par movement.py).
    Drain normalisé par max_force → power_idle et power_max_steer sont en %capacité/s.
    """
    mask = world.alive_mask

    thrust_ratio = (
        np.linalg.norm(raw_steering[mask], axis=1)
        / world.max_forces[mask]
    )  # [0.0 → 1.0]

    drain = (world.power_idle[mask] + world.power_max_steer[mask] * thrust_ratio) * dt

    # Modif in-place sur la vue — world.battery_levels retourne le array du ComponentStore
    levels = world.battery_levels
    levels[mask] -= drain
    levels[:]     = np.clip(levels, 0.0, 1.0)