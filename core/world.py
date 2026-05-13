# world.py

from core.config_loader import load_drone_configs
from entities.drone import Drone

class World:
    def __init__(self):
        self.drones: dict[int, Drone] = {} # id → Drone
        self._next_id = 0 
        self.drone_configs = load_drone_configs()   # charge et valide les configs de drones depuis JSON

    def add_drone(self, drone_type):
        config = self.drone_configs[drone_type]
        drone_id = self._next_id
        self.drones[drone_id] = Drone(id=drone_id, **config.model_dump())
        self._next_id += 1