# systems/decision.py
"""
Patrouille — cible glissante à vitesse constante.

Principe :
    patrol_d avance en continu (vitesse * dt) le long du périmètre.
    La target = zone.point_at(patrol_d), toujours sur le périmètre.
    Le drone poursuit cette cible glissante sans jamais avoir à la "toucher".

    → Marche pour les planeurs qui tournent mal : pas de condition d'arrivée,
      la cible glisse devant eux, ils suivent. Pas de blocage en cercle.

Vitesse de la cible :
    PATROL_SPEED en unités/seconde, commun à tous → équidistance préservée
    (patrol_d initiaux espacés de P/n, tous avancent pareil).

    À régler selon la vitesse réelle des drones : trop rapide, la cible
    s'échappe ; trop lent, les drones tournent en rond derrière.
"""

import numpy as np
from core.world import World
from entities.types import DroneMode

Coef_Patrouille_vitesse_maxmin = 0.9 # on fait bouger les points désrés à k * V avec V vitesse du plus lent élément du groupe

# ── Patrouille ────────────────────────────────────────────────────────────────

def _patrol(world: World, ctx, zone, dt: float) -> None:
    alive_ids = ctx.alive_ids
    if len(alive_ids) == 0:
        return
    patrol_speed_min = Coef_Patrouille_vitesse_maxmin * float(np.min(world.components.arr("speed")[alive_ids])) #LE GROUPE EST AUSSI FORT QUE SONT PLUS FAIBLE ELEMENTS !

    P        = zone.perimeter
    patrol_d = world.components.arr("patrol_progress")

    # Toutes les cibles glissent à la même vitesse → équidistance conservée
    patrol_d[alive_ids] = (patrol_d[alive_ids] + patrol_speed_min * dt) % P

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
