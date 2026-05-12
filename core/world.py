# world.py

from core.config_loader import load_drone_configs
from entities.drone import Drone

class World:
    def __init__(self):
        self.drones = {}
        self.drone_configs = load_drone_configs()

    def add_drone(self, drone_id, drone_type):
        config = self.drone_configs[drone_type]
        self.drones[drone_id] = Drone(drone_id, config)