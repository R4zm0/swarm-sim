# systems/battery.py
"""
Drain de batterie + passage en mode DEAD.

MODÈLE D'ÉNERGIE
────────────────
Chaque tick, un drone consomme :

    drain = (power_idle  +  power_max_steer * thrust_ratio) * dt

  - power_idle      : conso de base (rester en l'air / moteur tournant), même
                      sans manœuvrer. Constante par type de drone.
  - power_max_steer : conso supplémentaire à PLEINE poussée (thrust_ratio = 1).
  - thrust_ratio    : effort de manœuvre actuel, normalisé dans [0, 1] :

        thrust_ratio = ‖raw_steering‖ / max_force

    raw_steering est la force de steering AVANT division par la masse (cf.
    movement.py) : c'est donc une vraie force, comparable à max_force. La
    normaliser par max_force donne "quel pourcentage de ma poussée max
    j'utilise en ce moment" → 0 = vol plané, 1 = manœuvre à fond.

Cette convention (normaliser l'énergie par max_force) est l'approche standard des
moteurs physiques (Bullet, PhysX, Unity DOTS) : les coefficients d'énergie restent
sans unité et indépendants de l'échelle de force du drone.

SEUIL DE MORT
─────────────
DEAD_THRESHOLD = 0.2 : sous 20% le drone est retiré de la patrouille. Ce n'est PAS
0% volontairement : un vrai drone déclenche un retour-base / atterrissage de
sécurité avec une réserve. À 20%, decision.py détecte la baisse du nombre de
vivants et redistribue les survivants.
"""

import numpy as np
from core.world import World
from entities.types import DroneMode

# 20 % = seuil de retour/sécurité ; en-dessous le drone passe DEAD et quitte la patrouille.
DEAD_THRESHOLD = 0.2


def update(world: World, ctx, dt: float) -> None:
    alive_ids = ctx.alive_ids
    n_alive   = len(alive_ids)
    if n_alive == 0:
        return

    raw_steering = ctx.raw_steering

    # ── Alignement de raw_steering ────────────────────────────────────────────
    # Selon le chemin de code, movement peut renvoyer un tableau de taille N_total
    # (une ligne par drone, morts inclus) ou de taille N_alive (vivants seulement).
    # On gère les deux pour éviter le crash "boolean index did not match" qui
    # survenait quand un drone mourait entre la création du TickContext et ici.
    if raw_steering.shape[0] == len(world.alive_mask):
        steer_alive = raw_steering[alive_ids]   # tableau complet → on extrait les vivants
    else:
        steer_alive = raw_steering[:n_alive]    # déjà réduit aux vivants (ordre alive_ids)

    # thrust_ratio ∈ [0,1] : fraction de la poussée max utilisée à ce tick.
    # max(max_force, 1e-6) évite la division par zéro pour un max_force dégénéré.
    max_f = world.max_forces[alive_ids]
    thrust_ratio = np.linalg.norm(steer_alive, axis=1) / np.maximum(max_f, 1e-6)

    # Conso = base (idle) + part variable proportionnelle à l'effort de manœuvre.
    drain = (world.power_idle[alive_ids]
             + world.power_max_steer[alive_ids] * thrust_ratio) * dt

    # Décrément, borné dans [0,1]. battery_levels est une VUE sur l'array du store,
    # donc l'écriture indexée modifie bien l'état réel des drones.
    levels = world.battery_levels
    levels[alive_ids] = np.clip(levels[alive_ids] - drain, 0.0, 1.0)

    # Tout drone sous le seuil passe DEAD ; il sera exclu d'alive_ids au prochain tick
    # (via _sync_alive_mask), ce qui déclenchera la redistribution dans decision.py.
    for drone_id in alive_ids:
        if levels[drone_id] < DEAD_THRESHOLD:
            world.components.set("mode", drone_id, DroneMode.DEAD)