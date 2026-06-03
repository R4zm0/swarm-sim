# world.py

import numpy as np  
from core.config_loader import load_drone_configs
from entities.drone import Drone
import utils.math as math_utils


class World:
    def __init__(self, dimensions=(1200, 1080)): 
        self.W = dimensions[0]
        self.H = dimensions[1]
        self.drones: dict[int, Drone] = {} # id → Drone
        self._next_id = 0 
        self.drone_configs = load_drone_configs()   # charge et valide les configs de drones depuis JSON
        
    def add_drone(self, drone_type: str, position: np.ndarray | None = None):
        
        config = self.drone_configs[drone_type]
        drone_id = self._next_id
        
        drone = Drone(id=drone_id, **config.model_dump())

        drone.position = math_utils.clamp_to_world(position, self.W, self.H) if position is not None else np.zeros(2)



        self.drones[drone_id] = drone

        self._next_id += 1
        return drone



