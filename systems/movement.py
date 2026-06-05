# systems/movement.py
"""
Steering behaviors — Reynolds (1999).

update(world, desired_velocities, dt)
    desired_velocities : (N, 2) — calculé par decision.py, une target par drone
"""

import numpy as np
from core.world import World


def update(world: World, desired_velocities: np.ndarray, dt: float, ) -> np.ndarray:
    mask       = world.alive_mask
    max_forces = world.max_forces          # caché dans World, fixe
    masses     = world.masses              # caché dans World, fixe
    max_speeds = world.effective_speeds()  # boucle inévitable (battery/jamming)

    steering = desired_velocities[mask] - world.velocities[mask]
    steering = _clamp_norm(steering, max_forces[mask])
    raw_steering = steering.copy()
    
    steering /= masses[mask, np.newaxis]

    world.velocities[mask] += steering * dt
    world.velocities[mask]  = _clamp_norm(world.velocities[mask], max_speeds[mask])
    world.positions[mask]  += world.velocities[mask] * dt
    world.positions         = np.clip(world.positions, [0, 0], [world.W, world.H])
    
    return raw_steering  # pour battery.py

def _clamp_norm(vectors: np.ndarray, max_mag: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1)
    scale = np.where(norms > max_mag, max_mag / np.maximum(norms, 1e-6), 1.0)
    return vectors * scale[:, np.newaxis]

def desired_from_targets(positions: np.ndarray, targets: np.ndarray, max_speeds: np.ndarray) -> np.ndarray:
    directions = targets - positions
    norms = np.linalg.norm(directions, axis=1)
    normalized = directions / np.maximum(norms[:, np.newaxis], 1e-6)
    return normalized * max_speeds[:, np.newaxis]