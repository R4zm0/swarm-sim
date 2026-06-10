# core/world.py
"""
World — conteneur central de la simulation.

Architecture :
    ComponentStore  : tous les scalaires et objets par-drone.
                      Peuplé automatiquement depuis DroneConfig.model_dump().
                      Ajouter un champ = JSON + schemas.py, rien d'autre.

    positions  (N, 2) : source de vérité physique — vec2, hors ComponentStore
    velocities (N, 2)
    targets    (N, 2)
    alive_mask (N,)   : mis à jour en fin de tick via _sync_alive_mask()

    enemy_positions (E, 2) : ennemis fixes — hors système de drones

    Drone             : proxy léger — drone.battery_level lit/écrit directement
                        dans ComponentStore, zéro copie, zéro sync manuel.
"""

import numpy as np
from core.components import ComponentStore
from core.config_loader import load_drone_configs
from entities.drone import Drone
from entities.types import DroneMode
from utils.math import clamp_to_world


class World:
    W = 19200
    H = 10800

    # État initial d'un drone — fusionné avec config.model_dump() dans add_drone.
    _INITIAL_STATE: dict = {
        "battery_level":     1.0,
        "jamming_level":     0.0,
        "signal_quality":    1.0,
        "sensor_efficiency": 1.0,
        "mode":              DroneMode.ACTIVE,
        "patrol_progress":   0.0,
        "messages":          [],
        "team":              0,
    }

    def __init__(self) -> None:
        self.components    = ComponentStore()
        self.drone_configs = load_drone_configs()
        self.drones: dict[int, Drone] = {}
        self._next_id = 0

        # Vec2 arrays — shape (N, 2), hors ComponentStore
        self.positions  = np.zeros((0, 2), dtype=float)
        self.velocities = np.zeros((0, 2), dtype=float)
        self.targets    = np.zeros((0, 2), dtype=float)
        self.alive_mask = np.zeros(0, dtype=bool)

        # Ennemis fixes — pas dans le système de drones
        self.enemy_positions = np.zeros((0, 2), dtype=float)

    # ── Ajout de drones ───────────────────────────────────────────────────────

    def add_drone(self, drone_type: str, position: np.ndarray | None = None, team: int = 0) -> Drone:
        config   = self.drone_configs[drone_type]
        drone_id = self._next_id

        pos = clamp_to_world(
            position if position is not None else np.zeros(2),
            self.W, self.H,
        )

        self.components.push({**config.model_dump(), **self._INITIAL_STATE, "team": team})

        self.positions  = np.vstack([self.positions,  [pos]])
        self.velocities = np.vstack([self.velocities, [[0., 0.]]])
        self.targets    = np.vstack([self.targets,    [pos]])
        self.alive_mask = np.append(self.alive_mask, True)

        drone = Drone(drone_id, self)
        self.drones[drone_id] = drone
        self._next_id += 1
        return drone

    # ── Ajout d'ennemis ───────────────────────────────────────────────────────

    def add_enemy(self, position: np.ndarray) -> None:
        """Ennemi fixe — position seulement, pas de comportement."""
        pos = clamp_to_world(np.array(position, dtype=float), self.W, self.H)
        if len(self.enemy_positions) == 0:
            self.enemy_positions = np.array([pos], dtype=float)
        else:
            self.enemy_positions = np.vstack([self.enemy_positions, [pos]])

    # ── Propriétés — raccourcis vers les arrays fréquents ─────────────────────

    @property
    def max_forces(self) -> np.ndarray:
        return self.components.arr("max_force")

    @property
    def masses(self) -> np.ndarray:
        return self.components.arr("mass")

    @property
    def battery_levels(self) -> np.ndarray:
        return self.components.arr("battery_level")

    @property
    def power_idle(self) -> np.ndarray:
        return self.components.arr("power_idle")

    @property
    def power_max_steer(self) -> np.ndarray:
        return self.components.arr("power_max_steer")

    # ── Helpers vectorisés ────────────────────────────────────────────────────

    @property
    def live_positions(self) -> np.ndarray:
        return self.positions[self.alive_mask]

    @property
    def n_alive(self) -> int:
        return int(self.alive_mask.sum())

    def effective_speeds(self) -> np.ndarray:
        return np.array([d.effective_speed for d in self.drones.values()])

    # ── Sync ──────────────────────────────────────────────────────────────────

    def _sync_alive_mask(self) -> None:
        for drone_id, drone in self.drones.items():
            self.alive_mask[drone_id] = drone.is_alive

    def _sync_to_drones(self) -> None:
        self._sync_alive_mask()