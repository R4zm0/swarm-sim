from dataclasses import dataclass, field
from entities.types import DroneMode
import numpy as np
import math




@dataclass
class Drone:
    # --- config (chargée depuis JSON, immuable) ---
    id: int # identifiant unique, assigné par le World à la création du drone
    type: str # identifiant de type de drone, ex: scout_light, relay, carrier_heavy, par default c'est default pour l'instant c'est une spec pour le futur si on veut faire du polymorphisme de fonctions selon le type de drone
    display_name: str # nom d'affichage, pour les logs et l'interface
    
    speed: float 
    max_force: float        # amplitude max du vecteur de correction par tick
    mass: float             # inertie : plus c'est lourd, plus le virage est mou

    sensor_radius: float 
    comm_radius: float
    
    battery_capacity: float
    battery_model: str
    battery_knee: float
    battery_steepness: float

    power_idle: float
    power_max_steer: float

    # --- état cinématique ---
    position: np.ndarray = field(default_factory=lambda: np.zeros(2))
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(2))

    # --- mode opérationnel ---
    mode: DroneMode = DroneMode.ACTIVE 


    # --- dégradations continues [0.0 → 1.0] ---
    battery_level: float = 1.0       # 1 = pleine charge, 0 = vide
    jamming_level: float = 0.0       # 0 = aucun brouillage, 1 = totalement brouillé
    signal_quality: float = 1.0      # 0 = comm coupée, 1 = signal parfait
    sensor_efficiency: float = 1.0   # réduit par météo / terrain
    
    

    # --- comms ---
    messages: list = field(default_factory=list)


    def _lipo_factor(self) -> float:
        print(1.0 / (1.0 + math.exp(
            -self.battery_steepness * (self.battery_level - self.battery_knee)
        )))
        return 1.0 / (1.0 + math.exp(
            -self.battery_steepness * (self.battery_level - self.battery_knee)
        ))

    def _combustion_factor(self) -> float:
        return 1.0 if self.battery_level > 0.02 else 0.0

    def _linear_factor(self) -> float:
        return self.battery_level


    def __post_init__(self) -> None:
        match self.battery_model:
            case "combustion":
                self._battery_factor = self._combustion_factor
            case "lipo":
                self._battery_factor = self._lipo_factor
            case _:
                self._battery_factor = self._linear_factor

    @property
    def effective_speed(self) -> float:
        return self.speed * self._battery_factor()

    @property   
    def effective_sensor_radius(self) -> float:
        return self.sensor_radius * self.sensor_efficiency

    @property
    def effective_comm_radius(self) -> float:
        return self.comm_radius * self.signal_quality

    @property
    def is_alive(self) -> bool:
        return self.mode is not DroneMode.DEAD
