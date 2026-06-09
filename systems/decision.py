# systems/decision.py
"""
Comportements de navigation — écrit dans world.targets (N, 2).

Flux :
    decision.update(world, ctx, zone)
        → world.targets mis à jour
        → movement.py lit world.targets au tick suivant

Comportements :
    patrol      — patrouille équidistante sur le périmètre de zone
    separation  — répulsion entre alliés trop proches (anti-collision)

ctx  : TickContext (voir core/scheduler.py)
zone : PatrolZone  (voir environment/zone.py)
"""

import numpy as np
from core.world import World


# ── Patrouille ────────────────────────────────────────────────────────────────

def _patrol(world: World, ctx, zone) -> None:
    """
    Chaque drone se projette sur le périmètre, calcule sa progression courante,
    puis reçoit une target équidistante des autres drones + un lookahead.

    Pas d'état stocké — progress_from_position() recalcule depuis la position
    réelle à chaque tick. Auto-correctif, aucune erreur accumulée.

    Redistribution automatique : si un drone meurt, les survivants se projettent
    toujours sur le périmètre et les positions idéales se recalculent pour n-1.
    """
    alive_ids = ctx.alive_ids
    n         = len(alive_ids)
    if n == 0:
        return

    P         = zone.perimeter
    positions = world.positions[alive_ids]

    # 1. Projection de chaque drone sur le périmètre
    progresses = np.array([
        zone.progress_from_position(positions[i])
        for i in range(n)
    ])  # (N,)

    # 2. Tri par progression courante
    sort_order = np.argsort(progresses)
    base       = progresses[sort_order[0]]
    ideal_gap  = P / n

    # 3. Lookahead : avance en avance de la moitié d'un intervalle
    #    Clamp pour éviter que le lookahead dépasse le périmètre
    lookahead = min(ideal_gap * 0.4, 500.0)

    # 4. Target = position idéale + lookahead vers l'avant
    for rank in range(n):
        drone_idx      = sort_order[rank]
        drone_id       = alive_ids[drone_idx]
        ideal_progress = (base + rank * ideal_gap) % P
        target_d       = (ideal_progress + lookahead) % P
        world.targets[drone_id] = zone.point_at(target_d)


# ── Séparation ────────────────────────────────────────────────────────────────

def _separation(world: World, ctx, weight: float = 0.3) -> np.ndarray:
    """
    Force de répulsion entre alliés proches — anti-collision.
    Retourne un vecteur (N_alive, 2) normalisé.
    Pondéré par `weight` avant d'être combiné avec le patrol.
    """
    alive_ids = ctx.alive_ids
    ally_mask = ctx.detected & ctx.friendly

    safe_dist = np.where(ally_mask & (ctx.distances > 0), ctx.distances, np.inf)
    weights   = 1.0 / safe_dist ** 2

    forces = np.sum(ctx.diff * weights[:, :, np.newaxis], axis=1)  # (N, 2)

    norms  = np.linalg.norm(forces, axis=1, keepdims=True)
    return np.where(norms > 1e-6, forces / norms, 0.0) * weight


# ── Update principal ──────────────────────────────────────────────────────────

def update(world: World, ctx, zone=None) -> None:
    """
    Si zone fournie : comportement patrol + séparation.
    Sinon : séparation seule (fallback pour tests sans scénario).
    """
    alive_ids = ctx.alive_ids
    if len(alive_ids) == 0:
        return

    if zone is not None:
        _patrol(world, ctx, zone)
        # Ajuste légèrement les targets avec la force de séparation
        sep = _separation(world, ctx, weight=300.0)
        world.targets[alive_ids] += sep
        world.targets = np.clip(world.targets, [0, 0], [world.W, world.H])
    else:
        # fallback sans zone
        positions = world.positions[alive_ids]
        sep = _separation(world, ctx, weight=1.0)
        norms = np.linalg.norm(sep, axis=1, keepdims=True)
        sep   = np.where(norms > 1e-6, sep / norms, 0.0)
        world.targets[alive_ids] = positions + sep * 500.0
        world.targets = np.clip(world.targets, [0, 0], [world.W, world.H])