# main.py
import threading
import time
import numpy as np
from core.world import World
from visualization.renderer import run
from systems.movement import update, desired_from_targets

world = World()

world.add_drone("fpv", position=np.array([200.0, 300.0]))
world.targets[0] = np.array([700.0, 500.0])   # target du drone 0
world.drones[0].speed = 100 

def sim_loop():
    dt = 1 / 60
    while True:
        max_speeds = world.effective_speeds()  # recalculé à la demande via une boucle dans movement.py
        desired    = desired_from_targets(world.positions, world.targets, max_speeds)
        update(world, desired, dt)
        time.sleep(dt)
threading.Thread(target=sim_loop, daemon=True).start()
run(world)
