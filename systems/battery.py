# systems/battery.py
import numpy as np
from core.world import World

def update(world: World, steering_forces: np.ndarray, dt: float) -> None:
    """steering_forces : (N, 2) — le vecteur de correction calculé dans movement.py"""
    mask = world.alive_mask
    thrust_ratio = (np.linalg.norm(steering_forces[mask], axis=1) / world.max_forces[mask])

    power  = world.power_idle[mask] + world.power_max_steer[mask] * thrust_ratio
    drain  = power * dt  

    world.battery_levels[mask] -= drain
    world.battery_levels        = np.clip(world.battery_levels, 0.0, 1.0)
    