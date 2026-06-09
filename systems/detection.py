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


def update(world: World) -> tuple[np.ndarray, np.ndarray]:
    """
    Retourne :
        detected (N_alive, N_alive) bool
        friendly (N_alive, N_alive) bool


        pour chaque drone i, j :
        detected_friends = detected &  friendly
        detected_enemies = detected & ~friendly   # à la demande, une ligne
    """
    alive_ids = np.where(world.alive_mask)[0]
    n         = len(alive_ids)

    if n == 0:
        empty = np.zeros((0, 0), dtype=bool)
        return empty, empty

    positions = world.positions[alive_ids]                              # (N, 2)

    # diff[i, j] = vecteur de i vers j
    diff      = positions[np.newaxis, :, :] - positions[:, np.newaxis, :]  #    (1,N,2) - (N,1,2) ou vecteur de taile N de vecteur de R² = (N, N, 2)
    distances = np.linalg.norm(diff, axis=2)                               # (N, N) matrice des distnace entre chaque paire de drones vivants, symétrique, avec des 0 sur la diagonale

    sensor_radii = (
        world.components.arr("sensor_radius")[alive_ids]
        * world.components.arr("sensor_efficiency")[alive_ids]
    )  # (N,)

    # drone i détecte drone j si dist(i,j) < sensor_radius[i]
    in_range = distances < sensor_radii[:, np.newaxis]   # broadcast (N, N)
    np.fill_diagonal(in_range, False)                    # un drone ne se détecte pas lui-même

    # ── Ami / ennemi ──────────────────────────────────────────────────────────
    teams    = world.components.arr("team")[alive_ids]          # (N,)
    friendly = teams[:, np.newaxis] == teams[np.newaxis, :]     # (N, N) avec newaxis pour comparer chaque paire (i, j), à gauche de l'égalité ça repète en ligne, à droite en colonne

    detected = in_range
    return detected, friendly
    

def detected_by(
    detected: np.ndarray,
    friendly: np.ndarray,
) :
    """
    Utilitaire : pour chaque drone, liste des indices détectés amis / ennemis.
    Utile dans decision.py pour la logique individuelle.

    Retourne :
        friends_per_drone  list[np.ndarray]  — indices des amis détectés par drone i
        enemies_per_drone  list[np.ndarray]  — indices des ennemis détectés par drone i
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