# core/scheduler.py
"""
TickContext + Scheduler — orchestration d'un tick de simulation.

Ordre d'un tick :
    1. TickContext   — distances + détection
    2. decision      → world.targets
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
    alive_ids     (N,)        indices des drones vivants
    diff          (N, N, 2)   diff[i,j] = pos[i] - pos[j]
    distances     (N, N)      distances euclidiennes
    detected      (N, N) bool
    friendly      (N, N) bool
    raw_steering  (N_total, 2)
    """

    def __init__(self, world) -> None:
        self.alive_ids    = np.where(world.alive_mask)[0]
        self.raw_steering = np.zeros((len(world.alive_mask), 2))

        n = len(self.alive_ids)
        if n == 0:
            self.diff      = np.zeros((0, 0, 2))
            self.distances = np.zeros((0, 0))
            self.detected  = np.zeros((0, 0), dtype=bool)
            self.friendly  = np.zeros((0, 0), dtype=bool)
            return

        positions             = world.positions[self.alive_ids]
        self.diff, self.distances = distance_matrix(positions)
        self.detected, self.friendly = detection.update(
            world,
            distances=self.distances,
            alive_ids=self.alive_ids,
        )


class Scheduler:

    def __init__(self, zone=None, coverage_map=None) -> None:
        self.zone         = zone
        self.coverage_map = coverage_map
        self.tick_count   = 0

    def tick(self, world, dt: float) -> None:
        ctx = TickContext(world)

        if ctx.alive_ids.size == 0:
            return

        decision.update(world, ctx, self.zone)

        max_speeds       = world.effective_speeds()
        desired          = movement.desired_from_targets(world.positions, world.targets, max_speeds)
        ctx.raw_steering = movement.update(world, desired, dt)

        battery.update(world, ctx.raw_steering, dt)

        if self.coverage_map is not None:
            self.coverage_map.update(world)

        world._sync_alive_mask()
        self.tick_count += 1