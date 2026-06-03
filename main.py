# main.py
import threading
import time
import numpy as np
from core.world import World
from visualization.renderer import run

world = World()
world.add_drone("fpv", position=np.array([200.0, 300.0]))
drone = world.drones[0]
drone.velocity = np.array([150.0, 100.0])

def sim_loop():
    dt = 1 / 60
    while True:
        drone.position += drone.velocity * dt
        if drone.position[0] <= 0 or drone.position[0] >= world.W:
            drone.velocity[0] *= -1
        if drone.position[1] <= 0 or drone.position[1] >= world.H:
            drone.velocity[1] *= -1
        drone.position = np.clip(drone.position, [0, 0], [world.W, world.H])
        time.sleep(dt)

thread = threading.Thread(target=sim_loop, daemon=True)
thread.start()

run(world)  # bloquant, lit world.drones à chaque frame