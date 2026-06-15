# main.py
import json
import threading
import time
from core.scenario_loader import load
from core.scheduler import Scheduler
from core.save_load import load_state
from core.metrics_logger import MetricsLogger
from visualization.mission_select import run_select
from visualization.end_screen import show as show_end_screen
from visualization.renderer import run

import pygame


def main():
    # Boucle externe : menu → (session de sim) → menu → ...
    while True:
        result = run_select()
        if result is None:
            break   # l'utilisateur a fermé le menu

        world    = result["world"]
        zone     = result["zone"]
        coverage = result["coverage"]

        with open(result["scenario_path"]) as f:
            scenario_name = json.load(f).get("name", result["scenario_path"].stem)

        scheduler = Scheduler(zone=zone, coverage_map=coverage)

        if result["save_to_restore"] is not None:
            load_state(world, scheduler, coverage, result["save_to_restore"])

        logger = MetricsLogger(every=30)   # échantillonne la couverture tous les 30 ticks

        # ── État partagé sim / UI ────────────────────────────────────────────
        sim_state = {
            "paused":   False,
            "speed":    1.0,
            "step":     False,
            "running":  True,    # contrôle le thread de sim (coupé en fin de session)
            "finished": False,   # levé quand tous les drones sont morts
            "show_end": False,   # levé par la touche F (pause-bilan manuelle)
        }

        def sim_loop():
            dt = 1 / 60
            while sim_state["running"]:
                if sim_state["step"]:
                    scheduler.tick(world, dt)
                    sim_state["step"] = False
                elif not sim_state["paused"]:
                    scheduler.tick(world, dt)
                    logger.maybe_sample(scheduler.tick_count, world, coverage)
                    if world.n_alive == 0:
                        sim_state["finished"] = True
                time.sleep(dt / max(0.1, sim_state["speed"]))

        thread = threading.Thread(target=sim_loop, daemon=True)
        thread.start()

        # ── Boucle interne : renderer ↔ écran de fin (avec reprise possible) ──
        leave = "menu"   # ce qu'on fait en sortant de la session : "menu" ou "quit"
        while True:
            # Reset des flags de fin avant (re)lancement du renderer, sinon il
            # ressortirait aussitôt vers l'écran de fin en boucle.
            sim_state["show_end"] = False
            sim_state["finished"] = world.n_alive == 0

            outcome = run(
                world, zone, coverage, sim_state=sim_state,
                scheduler=scheduler, scenario_name=scenario_name,
                background_file=result.get("background"),
            )

            if outcome == "quit":
                leave = "quit"
                break

            # outcome == "end" → pause-bilan (le thread reste vivant, en pause)
            sim_state["paused"] = True
            action = show_end_screen(world, scheduler, coverage, logger, scenario_name)

            if action == "resume":
                sim_state["paused"] = False
                continue            # on rouvre le renderer sur le même monde
            else:
                leave = action       # "menu" ou "quit"
                break

        # Fin de session : on coupe proprement le thread de sim
        sim_state["running"] = False
        thread.join(timeout=1.0)

        if leave == "quit":
            break
        # sinon on reboucle vers run_select

    pygame.quit()


if __name__ == "__main__":
    main()