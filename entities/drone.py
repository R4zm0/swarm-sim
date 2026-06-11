# entities/drone.py
"""
Drone — proxy léger sur un slot dans World.components.

Toutes les données scalaires vivent dans world.components (ComponentStore).
drone.battery_level lit et écrit directement dans le numpy array du World —
pas de copie locale, toujours en sync, zéro sync manuel.

    drone.speed          → __getattr__ → components.get("speed", id)
    drone.battery_level  → __getattr__ → components.get("battery_level", id)
    drone.battery_level  = 0.5  → __setattr__ → components.set(...)
    drone.position       → property → world.positions[id]   (vue directe, pas de copie)
    drone.velocity       → property → world.velocities[id]
    drone.id             → property → self._id  (lecture seule)

Tous les champs de DroneConfig + _INITIAL_STATE sont accessibles sans
les déclarer ici — ils passent tous par __getattr__/__setattr__.
"""

import math
from entities.types import DroneMode
import numpy as np


class Drone:

    def __init__(self, drone_id: int, world) -> None:
        # Attributs privés — stockés dans __dict__ via object.__setattr__
        # Notre __setattr__ redirige tout ce qui commence par _ ici directement.
        self._id    = drone_id
        self._world = world

        # Battery factor swappé une fois à la création — zéro branchement au tick
        model = world.components.get("battery_model", drone_id)
        match model:
            case "combustion": self._battery_factor = self._combustion_factor
            case "lipo":       self._battery_factor = self._lipo_factor
            case _:            self._battery_factor = self._linear_factor

    # ── Proxy ComponentStore ──────────────────────────────────────────────────

    def __getattr__(self, name: str):
        """
        Appelé uniquement si l'attribut n'est pas dans __dict__ ni dans la classe.
        Couvre automatiquement tous les champs de DroneConfig + _INITIAL_STATE.
        """
        # Garde : _world peut ne pas encore être dans __dict__ pendant __init__
        world = self.__dict__.get("_world")
        if world is not None and name in world.components:
            return world.components.get(name, self.__dict__["_id"])
        raise AttributeError(f"Drone n'a pas de composant '{name}'")

    def __setattr__(self, name: str, value) -> None:
        if name.startswith("_"):
            # Attributs privés → __dict__ directement, pas de redirection
            object.__setattr__(self, name, value)
        elif name == "position":
            self._world.positions[self._id] = value
        elif name == "velocity":
            self._world.velocities[self._id] = value
        elif name in self._world.components:
            self._world.components.set(name, self._id, value)
        else:
            object.__setattr__(self, name, value)

    # ── Attributs spéciaux — hors ComponentStore ──────────────────────────────

    @property
    def id(self) -> int:
        return self._id

    @property
    def position(self) -> np.ndarray:
        """Vue directe sur world.positions[id] — pas de copie."""
        return self._world.positions[self._id]

    @property
    def velocity(self) -> np.ndarray:
        """Vue directe sur world.velocities[id] — pas de copie."""
        return self._world.velocities[self._id]

    # ── Batterie ──────────────────────────────────────────────────────────────
    # Méthodes swappées à la création dans __init__ — zéro branchement au tick.

    def _lipo_factor(self) -> float:
        arr = self._world.components.arr
        i   = self._id
        return 1.0 / (1.0 + math.exp(
            -arr("battery_steepness")[i] * (arr("battery_level")[i] - arr("battery_knee")[i])
        ))

    def _combustion_factor(self) -> float:
        return 1.0 if self._world.components.arr("battery_level")[self._id] > 0.02 else 0.0

    def _linear_factor(self) -> float:
        return float(self._world.components.arr("battery_level")[self._id])

    # ── Propriétés effectives ─────────────────────────────────────────────────

    @property
    def effective_speed(self) -> float:
        return self.speed * 1.0 * self._battery_factor()

    @property
    def effective_sensor_radius(self) -> float:
        return self.sensor_radius * self.sensor_efficiency

    @property
    def effective_comm_radius(self) -> float:
        return self.comm_radius * self.signal_quality

    @property
    def is_alive(self) -> bool:
        return self.mode is not DroneMode.DEAD