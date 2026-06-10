# systems/battery.py
"""
Drain de batterie + passage en mode DEAD quand la batterie est vide.

raw_steering peut avoir deux formes selon ce que movement.update retourne :
    - taille N_total (une ligne par drone, 0 pour les morts)
    - taille N_alive (une ligne par drone vivant, dans l'ordre de alive_ids)
On gère les deux cas pour éviter les désalignements de masque.
"""

import numpy as np
from core.world import World
from entities.types import DroneMode

DEAD_THRESHOLD = 0.2   # 20 % seuil de retour/sécurité, le drone est retiré de la patrouille


def update(world: World, raw_steering: np.ndarray, dt: float) -> None:
    alive_ids = np.where(world.alive_mask)[0]
    n_alive   = len(alive_ids)
    if n_alive == 0:
        return

    # Aligne raw_steering sur les drones vivants quelle que soit sa taille
    if raw_steering.shape[0] == len(world.alive_mask):
        steer_alive = raw_steering[alive_ids]      # array taille totale → on extrait les vivants
    else:
        steer_alive = raw_steering[:n_alive]       # array déjà réduit aux vivants

    max_f = world.max_forces[alive_ids]
    thrust_ratio = np.linalg.norm(steer_alive, axis=1) / np.maximum(max_f, 1e-6)

    drain = (world.power_idle[alive_ids]
             + world.power_max_steer[alive_ids] * thrust_ratio) * dt

    levels = world.battery_levels
    levels[alive_ids] = np.clip(levels[alive_ids] - drain, 0.0, 1.0)

    # Passe en DEAD les drones vidés
    for drone_id in alive_ids:
        if levels[drone_id] < DEAD_THRESHOLD:
            world.components.set("mode", drone_id, DroneMode.DEAD)