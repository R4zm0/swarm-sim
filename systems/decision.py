# systems/decision.py
"""
Comportements de navigation — écrit dans world.targets (N, 2).

Flux :
    decision.update(world, ctx, zone, dt)
        → world.targets mis à jour
        → movement.py lit world.targets au tick suivant

Comportements :
    patrol           — chaque drone avance patrol_d à sa propre vitesse
    react_to_enemy   — réaction quand un drone détecte un ennemi fixe

patrol_d avance de speed * dt par tick — pas de projection géométrique
pendant le trajet. Résultat déterministe, équidistance garantie par construction.
"""

import numpy as np
from core.world import World
from entities.types import DroneMode


# ── Patrouille ────────────────────────────────────────────────────────────────

def _patrol(world: World, ctx, zone, dt: float) -> None:
    """
    Avance patrol_progress de speed * dt par tick.
    Target = zone.point_at(patrol_d + lookahead).

    Pas de progress_from_position pendant le trajet — aucune ambiguïté
    sur quelle arête est la plus proche.

    Équidistance : garantie par les valeurs initiales i * P/n.
    Si un drone meurt, le gap se referme naturellement au prochain tour complet.
    """
    alive_ids = ctx.alive_ids
    n         = len(alive_ids)
    if n == 0:
        return

    P        = zone.perimeter
    lookahead = min(P / n * 0.35, 800.0)
    patrol_d  = world.components.arr("patrol_progress")
    speeds    = world.components.arr("speed")[alive_ids]

    # Avance patrol_d à la vitesse propre de chaque drone
    patrol_d[alive_ids] = (patrol_d[alive_ids] + speeds * dt) % P

    # Target = point sur le périmètre légèrement en avance
    for drone_id in alive_ids:
        world.targets[drone_id] = zone.point_at(
            (patrol_d[drone_id] + lookahead) % P
        )


# ── Réaction ennemi ───────────────────────────────────────────────────────────

def react_to_enemy(world: World, ctx) -> None:
    """
    Contact ennemi → mode EMERGENCY (rouge dans le renderer).
    Plus de contact → retour ACTIVE.
    Comportement de navigation inchangé — extension future ici.
    """
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
        # Fallback sans zone : séparation simple
        positions = world.positions[alive_ids]
        ally_mask = ctx.detected & ctx.friendly
        safe_dist = np.where(ally_mask & (ctx.distances > 0), ctx.distances, np.inf)
        weights   = 1.0 / safe_dist ** 2
        forces    = np.sum(ctx.diff * weights[:, :, np.newaxis], axis=1)
        norms     = np.linalg.norm(forces, axis=1, keepdims=True)
        sep       = np.where(norms > 1e-6, forces / norms, 0.0)
        world.targets[alive_ids] = positions + sep * 500.0
        world.targets = np.clip(world.targets, [0, 0], [world.W, world.H])