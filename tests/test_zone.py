"""
Tests unitaires — environment.zone.PatrolZone

4 méthodes testées (perimeter, point_at, contains, waypoints), 2+ cas chacune.
Lancer depuis la racine du projet :  python -m unittest tests.test_zone
"""

import unittest
import numpy as np
from environment.zone import PatrolZone


class TestPatrolZone(unittest.TestCase):

    def setUp(self):
        # Carré 100x100, périmètre = 400, premier sommet (0,0)
        self.square = PatrolZone([[0, 0], [100, 0], [100, 100], [0, 100]])

    # ── perimeter ─────────────────────────────────────────────────────────────

    def test_perimeter_square(self):
        self.assertAlmostEqual(self.square.perimeter, 400.0, places=6)

    def test_perimeter_triangle(self):
        # Triangle 3-4-5
        tri = PatrolZone([[0, 0], [3, 0], [0, 4]])
        self.assertAlmostEqual(tri.perimeter, 3 + 4 + 5, places=6)

    # ── point_at ──────────────────────────────────────────────────────────────

    def test_point_at_start(self):
        # d = 0 → premier sommet
        np.testing.assert_allclose(self.square.point_at(0.0), [0, 0])

    def test_point_at_mid_edge(self):
        # d = 50 → milieu de la première arête (bas)
        np.testing.assert_allclose(self.square.point_at(50.0), [50, 0])

    def test_point_at_wrap(self):
        # d > périmètre → wrap modulo P
        np.testing.assert_allclose(self.square.point_at(400.0), [0, 0], atol=1e-6)

    # ── contains ──────────────────────────────────────────────────────────────

    def test_contains_inside(self):
        self.assertTrue(self.square.contains(np.array([50, 50])))

    def test_contains_outside(self):
        self.assertFalse(self.square.contains(np.array([200, 200])))

    # ── waypoints ─────────────────────────────────────────────────────────────

    def test_waypoints_count(self):
        wps = self.square.waypoints(4)
        self.assertEqual(len(wps), 4)

    def test_waypoints_equidistant(self):
        # 4 points sur un carré → distances entre voisins consécutifs égales
        wps = self.square.waypoints(4)
        d01 = np.linalg.norm(wps[1] - wps[0])
        d12 = np.linalg.norm(wps[2] - wps[1])
        self.assertAlmostEqual(d01, d12, places=4)


if __name__ == "__main__":
    unittest.main()
