# systems/decision_extra.py
"""
Variante avancée — essaim hétérogène (vitesses ET rayons différents).

Même logique que decision.py (waypoint fixe + avance à l'arrivée),
mais le gap de chaque drone est pondéré par speed × sensor_radius_effectif.

Raisonnement :
    temps de parcours d'un gap g à vitesse v = g / v
    Pour que tous les drones arrivent "en même temps" : g ∝ v
    Pour que la couverture soit continue          : g ∝ sensor_radius
    Combined                                      : g ∝ v × r

    gap[i] = v[i] × r[i] / Σ(v[j] × r[j]) × P

Un drone lent à petit rayon occupe peu de périmètre.
Un drone rapide à grand rayon en occupe beaucoup.
Équivalent à decision.py quand tous les drones sont identiques.

Swap dans scheduler.py :
    import systems.decision_extra as decision
"""

import numpy as np
from core.world import World
from entities.types import DroneMode

REACH_THRESHOLD = 800.0


# ── Patrouille pondérée ───────────────────────────────────────────────────────

def _patrol(world: World, ctx, zone) -> None:
    """
    Waypoint following avec gaps pondérés par speed × sensor_radius.
    Fonctionne sur tout polygone (convexe ou non).
    """
    alive_ids = ctx.alive_ids
    n         = len(alive_ids)
    if n == 0:
        return

    P = zone.perimeter

    # ── Poids : speed × sensor_radius_effectif ────────────────────────────────
    speeds = world.components.arr("speed")[alive_ids]
    radii  = (
        world.components.arr("sensor_radius")[alive_ids]
        * world.components.arr("sensor_efficiency")[alive_ids]
    )
    combined = speeds * radii
    weights  = combined / combined.sum()    # (N,) — somme = 1.0

    patrol_d = world.components.arr("patrol_progress")

    for i, drone_id in enumerate(alive_ids):
        pos  = world.positions[drone_id]
        dist = np.linalg.norm(pos - world.targets[drone_id])

        if dist > REACH_THRESHOLD:
            continue

        # Gap proportionnel à ce drone
        my_gap = weights[i] * P
        patrol_d[drone_id] = (patrol_d[drone_id] + my_gap) % P
        world.targets[drone_id] = zone.point_at(patrol_d[drone_id])


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
        _patrol(world, ctx, zone)
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