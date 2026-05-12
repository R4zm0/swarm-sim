from dataclasses import dataclass, field
from entities.types import DroneMode, DroneRole
import numpy as np

@dataclass
class Drone:
    # --- config (chargée depuis JSON, immuable) ---
    id: str
    role: DroneRole
    speed: float
    sensor_radius: float
    comm_radius: float
    battery_capacity: float

    # --- état cinématique ---
    position: np.ndarray = field(default_factory=lambda: np.zeros(2))
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(2))

    # --- mode opérationnel ---
    mode: DroneMode = DroneMode.IDLE

    # --- dégradations continues [0.0 → 1.0] ---
    battery_level: float = 1.0       # 1 = pleine charge, 0 = vide
    jamming_level: float = 0.0       # 0 = aucun brouillage, 1 = totalement brouillé
    signal_quality: float = 1.0      # 0 = comm coupée, 1 = signal parfait
    sensor_efficiency: float = 1.0   # réduit par météo / terrain

    # --- comms ---
    messages: list = field(default_factory=list)

    @property
    def effective_speed(self) -> float:
        return self.speed * (1.0 - 0.5 * self.jamming_level) * self.battery_level

    @property
    def effective_sensor_radius(self) -> float:
        return self.sensor_radius * self.sensor_efficiency

    @property
    def effective_comm_radius(self) -> float:
        return self.comm_radius * self.signal_quality

    @property
    def is_alive(self) -> bool:
        return self.mode is not DroneMode.DEAD
