# core/scheduler.py
"""
TickContext + Scheduler — orchestration d'un tick de simulation.

Ordre d'un tick :
    1. TickContext   — distances + détection drones + contact ennemis
    2. decision      → world.targets  (+ réaction ennemis)
    3. movement      → positions, velocities  |  raw_steering → ctx
    4. battery       ← ctx.raw_steering
    5. coverage      → coverage_map
    6. _sync_alive_mask
"""

import numpy as np
import systems.decision  as decision
import systems.movement  as movement
import systems.battery   as battery
import systems.detection as detection
from utils.spatial import distance_matrix


class TickContext:
    """
    Données précalculées pour un seul tick — recréé à chaque tick.

    Attributs
    ---------
    alive_ids      (N,)        indices des drones vivants
    diff           (N, N, 2)   diff[i,j] = pos[i] - pos[j]
    distances      (N, N)      distances euclidiennes
    detected       (N, N) bool detected[i,j] = True si i détecte j
    friendly       (N, N) bool True si même équipe
    enemy_contact  (N,)   bool True si le drone i voit au moins un ennemi fixe
    raw_steering   (N_total, 2)
    """

    def __init__(self, world) -> None:
        self.alive_ids    = np.where(world.alive_mask)[0]
        self.raw_steering = np.zeros((len(world.alive_mask), 2))

        n = len(self.alive_ids)
        if n == 0:
            self.diff          = np.zeros((0, 0, 2))
            self.distances     = np.zeros((0, 0))
            self.detected      = np.zeros((0, 0), dtype=bool)
            self.friendly      = np.zeros((0, 0), dtype=bool)
            self.enemy_contact = np.zeros(0, dtype=bool)
            return

        positions             = world.positions[self.alive_ids]
        self.diff, self.distances = distance_matrix(positions)

        self.detected, self.friendly = detection.update(
            world,
            distances=self.distances,
            alive_ids=self.alive_ids,
        )
        # ── Contact ennemis fixes ─────────────────────────────────────────────
        E = len(world.enemy_positions)
        if E > 0:
            diff_e = positions[:, np.newaxis, :] - world.enemy_positions[np.newaxis, :, :]
            dist_e = np.linalg.norm(diff_e, axis=2)                    # (N, E)
            sensor_radii = (
                world.components.arr("sensor_radius")[self.alive_ids]
                * world.components.arr("sensor_efficiency")[self.alive_ids]
            )
            self.enemy_contact = np.any(dist_e < sensor_radii[:, np.newaxis], axis=1)
        else:
            self.enemy_contact = np.zeros(n, dtype=bool)


class Scheduler:
    """Orchestre un pas de simulation : pipeline fixe, chaque étape
    consomme la sortie de la précédente (cf. rapport §3.2)."""

    def __init__(self, zone=None, coverage_map=None) -> None:
        self.zone         = zone           # PatrolZone : géométrie du périmètre, arretes, permietre etc...
        self.coverage_map = coverage_map   # CoverageMap : métrique de couverture
        self.tick_count   = 0              # numéro du pas courant (sérialisé au save)

    def tick(self, world, dt: float) -> None:
        ctx = TickContext(world) # donnée précalculés à chaque tick

        if ctx.alive_ids.size == 0:        # plus aucun drone vivant, on fait rien
            # simulation terminé on fait rien
            # todo un choix de fin de simulation : écriture d'une fin, ou d'un pop up de fin.
            return
        #1
        decision.update(world, ctx, self.zone, dt)
        max_speeds       = world.effective_speeds()   # v_max × f(batterie) 
        
        #2
        desired = movement.desired_from_targets(world.positions, world.targets, max_speeds) 
        #renvoi les vecteurs vitesse max orientés vers leurs cibles pour chaque drone
        ctx.raw_steering = movement.update(world, desired, dt)   # Applique la force et la renvoi

        #3
        battery.update(world, ctx, dt)
        #4
        if self.coverage_map is not None:
            self.coverage_map.update(world)
        #5
        world._sync_alive_mask()
        self.tick_count += 1