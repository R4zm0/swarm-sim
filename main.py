# main.py
import threading
import time
import numpy as np
from core.world import World
from visualization.renderer import run
import systems.movement as movement
import systems.battery as battery
from core.components import ComponentStore  # ← nouveau
from entities.types import DroneMode        # ← nouveau, utilisé dans _INITIAL_STATE



world = World()
world.add_drone("fpv",      position=np.array([200.0, 300.0]), team=0)
world.add_drone("mavic_isr", position=np.array([500.0, 500.0]), team=1)
world.add_drone("fpv", position=np.array([200.0, 300.0]))
world.targets[0] = np.array([7000.0, 5000.0])   # target du drone 0
world.drones[0].speed = 1000 
world.max_forces[0] = 200 


def sim_loop():
    dt = 1 / 60 #
    while True:
        max_speeds = world.effective_speeds()  # recalculé à la demande via une boucle dans movement.py
        desired    = movement.desired_from_targets(world.positions, world.targets, max_speeds)
        raw_steering = movement.update(world, desired, dt) # fait avancer les drones, retourne le steering pour battery.py
        battery.update(world, raw_steering, dt)  # met à jour le niveau de batterie
        world._sync_to_drones()
        print("test")
        time.sleep(dt)
threading.Thread(target=sim_loop, daemon=True).start()
run(world)
