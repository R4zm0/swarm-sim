# core/metrics_logger.py
"""
MetricsLogger — suivi temporel des métriques de couverture.

Distinct de save_load : la save sert à REPRENDRE une mission, ce logger sert à
ANALYSER une mission (courbe de couverture, reward RL...).

Usage :
    logger = MetricsLogger(every=30)         # échantillonne tous les 30 ticks
    logger.maybe_sample(tick, world, coverage)   # appelé dans la boucle de sim
    logger.to_csv(path)                          # exporté depuis l'écran de fin

CSV produit (une ligne = un échantillon dans le temps) :
    tick, n_alive, coverage_ratio, mean_value, max_gap
"""

import csv
from pathlib import Path
from datetime import datetime

LOGS_DIR = Path("data/logs")


class MetricsLogger:

    def __init__(self, every: int = 30) -> None:
        self.every = max(1, every)
        self.rows: list[tuple] = []   # (tick, n_alive, ratio, mean, max_gap)

    # ── Accumulation ──────────────────────────────────────────────────────────
    def maybe_sample(self, tick: int, world, coverage) -> None:
        """Enregistre un point si tick est un multiple de `every`."""
        if coverage is None or tick % self.every != 0:
            return
        m = coverage.metrics()
        self.rows.append((
            tick,
            world.n_alive,
            m["coverage_ratio"],
            m["mean_value"],
            m["max_gap"],
        ))

    # ── Résumé (pour l'écran de fin) ──────────────────────────────────────────
    def summary(self) -> dict:
        if not self.rows:
            return {"n_samples": 0}
        ratios = [r[2] for r in self.rows]
        means  = [r[3] for r in self.rows]
        gaps   = [r[4] for r in self.rows]
        return {
            "n_samples":  len(self.rows),
            "final_tick": self.rows[-1][0],
            "ratio_mean": sum(ratios) / len(ratios),
            "ratio_min":  min(ratios),
            "ratio_max":  max(ratios),
            "mean_mean":  sum(means) / len(means),
            "gap_max":    max(gaps),
        }

    # ── Export CSV ────────────────────────────────────────────────────────────
    def to_csv(self, path: str | Path | None = None, scenario_name: str = "run") -> Path:
        if path is None:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = LOGS_DIR / f"{scenario_name}_{ts}.csv"
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["tick", "n_alive", "coverage_ratio", "mean_value", "max_gap"])
            w.writerows(self.rows)
        return path
