# systems/detection.py
"""
Système de détection — qui voit qui dans son sensor_radius effectif.

update() retourne deux matrices (N_alive × N_alive) :
    detected  — detected[i, j] = True si le drone i détecte le drone j
    friendly  — True si même équipe, False si ennemie

Ces matrices sont passées en entrée aux systèmes qui en dépendent :
    comms.py     → ne propage les infos qu'entre drones qui se détectent
    decision.py  → un drone ajuste sa trajectoire selon ce qu'il voit

Indices : correspondent aux drones vivants dans l'ordre de world.alive_mask.
Pour retrouver l'id réel : alive_ids = np.where(world.alive_mask)[0]
"""

import numpy as np
from core.world import World
from utils.spatial import distance_matrix


def update(
    world:     World,
    distances: np.ndarray | None = None,   # précalculé par TickContext si dispo
    alive_ids: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Retourne :
        detected (N_alive, N_alive) bool
        friendly (N_alive, N_alive) bool
    """
    if alive_ids is None:
        alive_ids = np.where(world.alive_mask)[0]

    n = len(alive_ids)
    if n == 0:
        empty = np.zeros((0, 0), dtype=bool)
        return empty, empty

    if distances is None:
        positions        = world.positions[alive_ids]
        _, distances     = distance_matrix(positions)

    # ── Dans le rayon ────────────────────────────────────────────────────────
    sensor_radii = (
        world.components.arr("sensor_radius")[alive_ids]
        * world.components.arr("sensor_efficiency")[alive_ids]
    )  # (N,)

    # drone i détecte drone j si dist(i,j) < sensor_radius[i]
    in_range = distances < sensor_radii[:, np.newaxis]   # broadcast (N, N)
    np.fill_diagonal(in_range, False)                    # un drone ne se détecte pas lui-même

    # ── Ami / ennemi ──────────────────────────────────────────────────────────
    teams    = world.components.arr("team")[alive_ids]
    friendly = teams[:, np.newaxis] == teams[np.newaxis, :]

    return in_range, friendly


def detected_by(
    detected: np.ndarray,
    friendly: np.ndarray,
) -> tuple[list, list]:
    """
    Utilitaire : pour chaque drone, liste des indices détectés amis / ennemis.
    Utile dans decision.py pour la logique individuelle.

    Retourne :
        friends_per_drone  list[np.ndarray]
        enemies_per_drone  list[np.ndarray]
    """
    friends_per_drone = [
        np.where(detected[i] &  friendly[i])[0]
        for i in range(len(detected))
    ]
    enemies_per_drone = [
        np.where(detected[i] & ~friendly[i])[0]
        for i in range(len(detected))
    ]
    return friends_per_drone, enemies_per_drone