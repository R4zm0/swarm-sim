# environment/zone.py
"""
PatrolZone — polygone de patrouille.

Représente la frontière que les drones doivent parcourir.
Chargée depuis un scénario JSON — sera éditée via GUI plus tard.

Opérations clés :
    waypoints(n)              — n points équidistants sur le périmètre
    point_at(d)               — point à la distance d sur le périmètre
    progress_from_position(p) — projette une position 2D sur le périmètre
    contains(pt)              — point à l'intérieur ? (détection intrus)
"""

import numpy as np


class PatrolZone:

    def __init__(self, vertices: np.ndarray) -> None:
        """
        vertices : (M, 2) — sommets du polygone dans l'ordre.
        Le polygone est automatiquement fermé.
        """
        self.vertices = np.array(vertices, dtype=float)   # (M, 2)
        self._edges   = self._compute_edges()

    # ── Géométrie interne ─────────────────────────────────────────────────────

    def _compute_edges(self) -> list[dict]:
        """Précalcule arêtes + longueurs + cumul. Appelé une seule fois."""
        v, n  = self.vertices, len(self.vertices)
        edges = []
        cumul = 0.0
        for i in range(n):
            start  = v[i]
            end    = v[(i + 1) % n]
            length = float(np.linalg.norm(end - start))
            edges.append({"start": start, "end": end, "length": length, "cumul": cumul})
            cumul += length
        return edges

    @property
    def perimeter(self) -> float:
        return sum(e["length"] for e in self._edges)

    # ── Navigation sur le périmètre ───────────────────────────────────────────

    def point_at(self, d: float) -> np.ndarray:
        """
        Point sur le périmètre à la distance d depuis le premier sommet.
        Interpole linéairement sur l'arête correspondante.
        Wrap automatique si d > perimeter.
        """
        d = d % self.perimeter
        for edge in self._edges:
            local = d - edge["cumul"]
            if local <= edge["length"]:
                t = local / edge["length"] if edge["length"] > 0 else 0.0
                return edge["start"] + t * (edge["end"] - edge["start"])
        return self.vertices[-1].copy()

    def progress_from_position(self, point: np.ndarray) -> float:
        """
        Projette une position 2D sur le périmètre.
        Retourne la distance curviligne depuis le premier sommet.

        Utilisé dans decision.py pour connaître la progression courante
        d'un drone sans stocker d'état — auto-correctif, pas d'erreur accumulée.
        """
        best_dist = float("inf")
        best_d    = 0.0
        for edge in self._edges:
            seg = edge["end"] - edge["start"]
            if edge["length"] < 1e-6:
                continue
            t       = np.dot(point - edge["start"], seg) / (edge["length"] ** 2)
            t       = float(np.clip(t, 0.0, 1.0))
            closest = edge["start"] + t * seg
            dist    = float(np.linalg.norm(point - closest))
            if dist < best_dist:
                best_dist = dist
                best_d    = edge["cumul"] + t * edge["length"]
        return best_d

    def waypoints(self, n: int) -> np.ndarray:
        """
        Retourne n points équidistants sur le périmètre.
        Utilisé par scenario_loader pour placer les drones initialement.
        """
        step = self.perimeter / n
        return np.array([self.point_at(k * step) for k in range(n)], dtype=float)

    # ── Détection intrus ──────────────────────────────────────────────────────

    def contains(self, point: np.ndarray) -> bool:
        """Ray casting — True si le point est à l'intérieur du polygone."""
        x, y   = float(point[0]), float(point[1])
        inside = False
        v, n   = self.vertices, len(self.vertices)
        j      = n - 1
        for i in range(n):
            xi, yi = v[i]
            xj, yj = v[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    # ── Sérialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {"vertices": self.vertices.tolist()}

    @classmethod
    def from_dict(cls, data: dict) -> "PatrolZone":
        return cls(vertices=data["vertices"])