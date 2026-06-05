# core/world.py
"""
World : conteneur central de la simulation.

Deux niveaux de représentation coexistent :
    - self.drones (dict id → Drone) : logique individuelle, comportements, états
    - arrays numpy N×2 / N : calculs vectorisés

Arrays numpy :
    positions   (N, 2)  — source de vérité physique
    velocities  (N, 2)
    alive_mask  (N,)    — False = DEAD, jamais supprimé
    max_forces  (N,)    — fixe, caché à add_drone
    masses      (N,)    — fixe, caché à add_drone
    targets     (N, 2)  — target de navigation, écrit par decision.py

effective_speed n'est pas caché — dépend de battery/jamming propre à chaque drone,
recalculé à la demande via une boucle dans movement.py.
"""

import numpy as np
from core.config_loader import load_drone_configs
from entities.drone import Drone
from entities.types import DroneMode
from utils.math import clamp_to_world


class World:
    W = 19200
    H = 10800

    def __init__(self) -> None:
        self.drones        : dict[int, Drone] = {}
        self._next_id      = 0
        self.drone_configs = load_drone_configs()

        # shape (N, 2)
        self.positions  = np.zeros((0, 2), dtype=float)
        self.velocities = np.zeros((0, 2), dtype=float)
        self.targets    = np.zeros((0, 2), dtype=float)
        # shape (N,)
        self.alive_mask = np.zeros(0, dtype=bool)
        self.max_forces = np.zeros(0, dtype=float)   # fixe
        self.masses     = np.zeros(0, dtype=float)   # fixe

        # core/world.py
        self.battery_levels    = np.ones(0)          # (N,)  — état, mutable
        self.battery_capacities = np.zeros(0)        # (N,)  — fixe, caché à add_drone
        
        self.power_idle        = np.zeros(0)         # (N,)  — fixe
        self.power_max_steer       = np.zeros(0)         # (N,)  — fixe

    # ── Ajout de drones ───────────────────────────────────────────────────────

    def add_drone(
        self,
        drone_type: str,
        position: np.ndarray | None = None,
    ) -> Drone:
        config   = self.drone_configs[drone_type]
        drone_id = self._next_id
        drone    = Drone(id=drone_id, **config.model_dump())

        pos = clamp_to_world(
            position if position is not None else np.zeros(2),
            self.W, self.H,
        )
        drone.position = pos.copy()

        self.drones[drone_id] = drone

        self.positions  = np.vstack([self.positions,  [pos]])
        self.velocities = np.vstack([self.velocities, [drone.velocity]])
        self.targets    = np.vstack([self.targets,    [pos]])       # target = position initiale
        self.alive_mask = np.append(self.alive_mask, True)
        self.max_forces = np.append(self.max_forces, config.max_force)
        self.masses     = np.append(self.masses,     config.mass)

        self.battery_levels     = np.append(self.battery_levels,     1.0)
        self.battery_capacities = np.append(self.battery_capacities, config.battery_capacity)
        self.power_max_steer        = np.append(self.power_max_steer,        config.power_max_steer) # entre 0 et 1 combien de pourcentage de batterie par tick pour FORCE MAX
        self.power_idle             = np.append(self.power_idle,             config.power_idle)        # entre 0 et 1 combien de pourcentage de batterie par tick au repos

        self._next_id += 1  
        return drone

    # ── Sync individuel ───────────────────────────────────────────────────────

    def sync_from_drone(self, drone_id: int) -> None:
        """Sync position + velocity d'un Drone vers les arrays."""
        drone = self.drones[drone_id]
        self.positions[drone_id]  = drone.position
        self.velocities[drone_id] = drone.velocity

    def sync_velocity(self, drone_id: int, velocity: np.ndarray) -> None:
        self.drones[drone_id].velocity = velocity.copy()
        self.velocities[drone_id]      = velocity

    def sync_position(self, drone_id: int, position: np.ndarray) -> None:
        self.drones[drone_id].position = position.copy()
        self.positions[drone_id]       = position

    # ── Accesseurs vectorisés ─────────────────────────────────────────────────

    @property
    def live_positions(self) -> np.ndarray:
        return self.positions[self.alive_mask]

    @property
    def live_velocities(self) -> np.ndarray:
        return self.velocities[self.alive_mask]

    @property
    def n_alive(self) -> int:
        return int(self.alive_mask.sum())

    def effective_speeds(self) -> np.ndarray:
        """
        Recalculé à chaque appel : dépend de battery/jamming propre à chaque drone.
        Boucle inévitable : la formule peut différer par type de drone.
        """
        return np.array([d.effective_speed for d in self.drones.values()])
    
    # ── Interne ───────────────────────────────────────────────────────────────

    def _sync_alive_mask(self) -> None:
        for drone_id, drone in self.drones.items():
            self.alive_mask[drone_id] = drone.is_alive

    def _sync_to_drones(self) -> None:
        for drone_id, drone in self.drones.items():
            drone.position = self.positions[drone_id]
            drone.velocity = self.velocities[drone_id]
            drone.battery_level = self.battery_levels[drone_id]
        self._sync_alive_mask()