# systems/coverage.py
"""
CoverageMap — suivi de la couverture du périmètre par les drones.

Chaque point d'échantillonnage sur le périmètre a une valeur [0.0 → 1.0] :
    1.0 = couvert à l'instant
    0.0 = jamais vu (ou complètement oublié)

Paramètres configurables depuis le scénario JSON :
    n_samples         : résolution de la carte (points sur le périmètre)
    decay             : taux d'oubli par tick. 0 = mémoire parfaite (cumulatif),
                        0.001 = oubli lent (~11s à 60fps), 0.01 = rapide (~1s)
    covered_threshold : valeur min pour compter un point comme couvert [0,1]

Métriques disponibles (compatibles reward RL) :
    coverage_ratio    : fraction couverte maintenant [0,1]
    mean_value        : qualité lissée — utile comme reward continu
    max_gap           : plus grand trou en fraction du périmètre [0,1]
"""

import numpy as np
from environment.zone import PatrolZone


class CoverageMap:

    def __init__(
        self,
        zone:              PatrolZone,
        n_samples:         int   = 500,
        decay:             float = 0.0,
        covered_threshold: float = 0.5,
    ) -> None:
        self.zone      = zone
        self.n         = n_samples
        self.decay     = decay
        self.threshold = covered_threshold

        # Points d'échantillonnage équidistants sur le périmètre — (n, 2)
        self.points = zone.waypoints(n_samples)
        self.values = np.zeros(n_samples, dtype=float)   # [0.0 → 1.0]

    # ── Mise à jour ───────────────────────────────────────────────────────────

    def update(self, world) -> None:
        """
        Appelé à chaque tick par le scheduler.
        1. Decay  — l'info ancienne perd de la valeur.
        2. Mark   — les points dans le sensor_radius d'un drone passent à 1.0.
        """
        # 1. Decay
        if self.decay > 0.0:
            self.values *= (1.0 - self.decay)

        # 2. Mark — vectorisé (N drones × n_samples points)
        alive_ids = np.where(world.alive_mask)[0]
        if len(alive_ids) == 0:
            return

        positions    = world.positions[alive_ids]              # (N, 2)
        sensor_radii = (
            world.components.arr("sensor_radius")[alive_ids]
            * world.components.arr("sensor_efficiency")[alive_ids]
        )                                                      # (N,)

        # diff[i, j] = drone_i → point_j
        diff      = positions[:, np.newaxis, :] - self.points[np.newaxis, :, :]  # (N, n, 2)
        distances = np.linalg.norm(diff, axis=2)                                  # (N, n)

        # point j couvert si au moins un drone est dans son rayon
        covered          = np.any(distances < sensor_radii[:, np.newaxis], axis=0)
        self.values[covered] = 1.0

    # ── Métriques ─────────────────────────────────────────────────────────────

    @property
    def coverage_ratio(self) -> float:
        """Fraction du périmètre couverte en ce moment [0 → 1]."""
        return float(np.mean(self.values >= self.threshold))

    @property
    def mean_value(self) -> float:
        """
        Valeur moyenne des points [0 → 1].
        Métrique continue — meilleure que coverage_ratio pour un reward RL.
        """
        return float(np.mean(self.values))

    @property
    def max_gap(self) -> float:
        """
        Plus grand trou non couvert, en fraction du périmètre [0 → 1].
        0.0 = couverture parfaite. Mesure directe de l'équidistance.
        """
        uncovered = (self.values < self.threshold).astype(int)
        if uncovered.sum() == 0:
            return 0.0

        # Plus longue séquence consécutive — avec wrap (périmètre cyclique)
        doubled = np.concatenate([uncovered, uncovered])
        max_run = current = 0
        for v in doubled:
            current = current + 1 if v else 0
            max_run = max(max_run, current)
        return float(min(max_run, self.n) / self.n)

    def metrics(self) -> dict[str, float]:
        """Toutes les métriques en un dict — pour logs ou reward RL."""
        return {
            "coverage_ratio": self.coverage_ratio,
            "mean_value":     self.mean_value,
            "max_gap":        self.max_gap,
        }

    # ── Sérialisation ─────────────────────────────────────────────────────────

    def state_dict(self) -> dict:
        """Pour save/load de mission."""
        return {"values": self.values.tolist()}

    def load_state(self, state: dict) -> None:
        self.values = np.array(state["values"], dtype=float)

    # ── Constructeur depuis scénario JSON ─────────────────────────────────────

    @classmethod
    def from_scenario(cls, zone: PatrolZone, data: dict) -> "CoverageMap":
        """
        Charge les paramètres depuis le bloc 'coverage' du scénario.
        Tous les champs sont optionnels — valeurs par défaut si absent.
        """
        cfg = data.get("coverage", {})
        return cls(
            zone              = zone,
            n_samples         = cfg.get("n_samples",  500),
            decay             = cfg.get("decay",      0.0),
            covered_threshold = cfg.get("threshold",  0.5),
        )