# utils/spatial.py
"""
Primitives géométriques pures — sans état, sans dépendance au World.
Utilisées par detection.py, decision.py, comms.py.
"""

import numpy as np


def distance_matrix(positions: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Calcule toutes les paires de distances entre N points.

    diff[i, j]      = pos[i] - pos[j]   → vecteur de j vers i (direction répulsion)
    distances[i, j] = ||diff[i, j]||    → scalaire, symétrique

    Paramètres
    ----------
    positions : (N, 2)

    Retourne
    --------
    diff      : (N, N, 2)
    distances : (N, N)
    """
    diff      = positions[:, np.newaxis, :] - positions[np.newaxis, :, :]
    distances = np.linalg.norm(diff, axis=2)
    return diff, distances