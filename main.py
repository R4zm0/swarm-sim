# main.py
import threading
import time
from core.scenario_loader import load
from core.scheduler import Scheduler
from visualization.renderer import run

world, zone, coverage = load("data/scenarios/scenario_example.json")
scheduler = Scheduler(zone=zone, coverage_map=coverage)

# État partagé renderer ↔ sim loop
sim_state = {
    "paused": False,
    "speed":  1.0,    # multiplicateur : 0.25 / 0.5 / 1 / 2 / 4 / 8
    "step":   False,  # True = avancer d'un tick puis repasser à False
}

def sim_loop():
    dt = 1 / 60
    while True:
        if sim_state["step"]:
            scheduler.tick(world, dt)
            sim_state["step"] = False
        elif not sim_state["paused"]:
            scheduler.tick(world, dt)
        time.sleep(dt / max(0.1, sim_state["speed"]))

threading.Thread(target=sim_loop, daemon=True).start()
run(world, zone, coverage, sim_state=sim_state)