# systems/decision.py
"""
Comportements de navigation — écrit dans world.targets (N, 2).

Flux :
    decision.update(world, detected, friendly)
        → world.targets mis à jour
        → movement.py lit world.targets au tick suivant

Comportements implémentés :
    separation  — répulsion entre alliés proches, vectorisé
"""

import numpy as np
from core.world import World
from utils.spatial import distance_matrix


# ── Séparation ────────────────────────────────────────────────────────────────

def separation_forces(
    diff:      np.ndarray,   # (N, N, 2) — diff[i,j] = pos[i] - pos[j]
    distances: np.ndarray,   # (N, N)
    ally_mask: np.ndarray,   # (N, N) bool — True si j est un allié détecté de i
    min_dist:  float = 1.0,  # évite division par zéro
) -> np.ndarray:
    """
    Force de répulsion de i par rapport à tous ses alliés détectés j.

        F[i] = Σ_j  (pos[i] - pos[j]) / dist(i,j)²   pour j allié dans rayon

    Plus j est proche, plus il repousse fort (inverse distance²).

    Retourne
    --------
    forces : (N, 2) — non normalisé, à combiner avec les autres comportements
    """
    # évite division par zéro sur la diagonale et hors rayon
    safe_dist = np.where(ally_mask & (distances > 0), distances, np.inf)
    weights   = 1.0 / safe_dist ** 2           # (N, N) — 0 hors rayon

    # Σ_j diff[i,j] * weight[i,j]
    forces = np.sum(
        diff * weights[:, :, np.newaxis],       # (N, N, 2)
        axis=1,                                 # → (N, 2)
    )
    return forces


# ── Update principal ──────────────────────────────────────────────────────────

def update(
    world:     World,
    ctx : TickContext,   # (N_alive, N_alive) bool
) -> None:
    detected = ctx.detected
    friendly = ctx.friendly

    """
    Calcule les targets de navigation et les écrit dans world.targets.

    Comportement actuel : separation uniquement.
    À étendre : cohésion, alignment, seek target, flee enemy...
    """
    alive_ids = np.where(world.alive_mask)[0]
    if len(alive_ids) == 0:
        return

    positions  = world.positions[alive_ids]           # (N, 2)
    diff, distances = distance_matrix(positions)

    ally_mask  = detected & friendly                  # (N, N)

    sep = separation_forces(diff, distances, ally_mask)  # (N, 2)

    # Normalise — direction pure, magnitude gérée par movement.py
    norms = np.linalg.norm(sep, axis=1, keepdims=True)
    sep   = np.where(norms > 1e-6, sep / norms, 0.0)

    # Écrit dans world.targets — movement.py s'en charge au tick suivant
    # Pour l'instant : target = position + direction de séparation
    # À combiner avec d'autres comportements (seek, flee...) plus tard
    world.targets[alive_ids] = positions + sep * 500.0
    world.targets = np.clip(world.targets, [0, 0], [world.W, world.H])