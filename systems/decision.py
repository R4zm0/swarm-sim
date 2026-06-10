# systems/decision.py
"""
Patrouille — cible glissante + redistribution à la mort d'un drone.

patrol_d : position cible de chaque drone sur le périmètre.
    Avance en continu à PATROL_SPEED (commun → équidistance préservée).

Redistribution :
    Quand le nombre de drones vivants change (mort), on ré-espace les patrol_d
    des survivants équidistants, en partant de leur ordre actuel sur le périmètre.
    Fait UNE SEULE FOIS au changement, pas à chaque tick.
"""

import numpy as np
from core.world import World
from entities.types import DroneMode

PATROL_SPEED = 900.0   # vitesse de glissement de la cible (unités/s)

# Mémorise le nombre de vivants au tick précédent pour détecter une mort
_last_alive_count = {"n": -1}


# ── Patrouille ────────────────────────────────────────────────────────────────

def _redistribute(world: World, alive_ids: np.ndarray, zone) -> None:
    """Ré-espace les patrol_d des survivants équidistants, ordre courant conservé."""
    P        = zone.perimeter
    patrol_d = world.components.arr("patrol_progress")
    n        = len(alive_ids)
    if n == 0:
        return

    # Trie les survivants par leur position courante sur le périmètre
    current = patrol_d[alive_ids]
    order   = np.argsort(current)
    base    = current[order[0]]

    # Ré-assigne des positions équidistantes depuis le premier, ordre conservé
    for rank, local_idx in enumerate(order):
        drone_id = alive_ids[local_idx]
        patrol_d[drone_id] = (base + rank * P / n) % P


def _patrol(world: World, ctx, zone, dt: float) -> None:
    alive_ids = ctx.alive_ids
    n         = len(alive_ids)
    if n == 0:
        return

    # Détecte une mort → redistribue une seule fois
    if n != _last_alive_count["n"]:
        _redistribute(world, alive_ids, zone)
        _last_alive_count["n"] = n

    P        = zone.perimeter
    patrol_d = world.components.arr("patrol_progress")

    # Glissement commun → équidistance conservée
    patrol_d[alive_ids] = (patrol_d[alive_ids] + PATROL_SPEED * dt) % P

    for drone_id in alive_ids:
        world.targets[drone_id] = zone.point_at(patrol_d[drone_id] % P)


# ── Réaction ennemi ───────────────────────────────────────────────────────────

def react_to_enemy(world: World, ctx) -> None:
    for local_i, drone_id in enumerate(ctx.alive_ids):
        if ctx.enemy_contact[local_i]:
            world.components.set("mode", drone_id, DroneMode.EMERGENCY)
        elif world.components.get("mode", drone_id) is DroneMode.EMERGENCY:
            world.components.set("mode", drone_id, DroneMode.ACTIVE)


# ── Update principal ──────────────────────────────────────────────────────────

def update(world: World, ctx, zone=None, dt: float = 1/60) -> None:
    alive_ids = ctx.alive_ids
    if len(alive_ids) == 0:
        return

    react_to_enemy(world, ctx)

    if zone is not None:
        _patrol(world, ctx, zone, dt)
    else:
        positions = world.positions[alive_ids]
        ally_mask = ctx.detected & ctx.friendly
        safe_dist = np.where(ally_mask & (ctx.distances > 0), ctx.distances, np.inf)
        weights   = 1.0 / safe_dist ** 2
        forces    = np.sum(ctx.diff * weights[:, :, np.newaxis], axis=1)
        norms     = np.linalg.norm(forces, axis=1, keepdims=True)
        sep       = np.where(norms > 1e-6, forces / norms, 0.0)
        world.targets[alive_ids] = positions + sep * 500.0
        world.targets = np.clip(world.targets, [0, 0], [world.W, world.H])