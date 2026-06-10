# main.py
import threading
import time
from core.scheduler import Scheduler
from core.save_load import load_state
from visualization.mission_select import run_select
from visualization.renderer import run

# ── Sélection de mission ───────────────────────────────────────────────────────
result = run_select()
if result is None:
    exit()

world     = result["world"]
zone      = result["zone"]
coverage  = result["coverage"]
save_path = str(result["scenario_path"]).replace("scenarios", "saves")

scheduler = Scheduler(zone=zone, coverage_map=coverage)

if result["save_to_restore"] is not None:
    load_state(world, scheduler, coverage, result["save_to_restore"])

# ── Sim ───────────────────────────────────────────────────────────────────────
sim_state = {"paused": False, "speed": 1.0, "step": False}

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
run(world, zone, coverage, sim_state=sim_state, scheduler=scheduler, save_path=save_path)