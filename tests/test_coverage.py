"""
Tests unitaires — systems.coverage.CoverageMap

4 méthodes/propriétés testées (init, coverage_ratio, mean_value, max_gap),
2+ cas chacune.
"""

import unittest
import numpy as np
from environment.zone import PatrolZone
from systems.coverage import CoverageMap


class TestCoverageMap(unittest.TestCase):

    def setUp(self):
        self.zone = PatrolZone([[0, 0], [100, 0], [100, 100], [0, 100]])
        self.cov  = CoverageMap(self.zone, n_samples=100, decay=0.0, covered_threshold=0.5)

    # ── init ──────────────────────────────────────────────────────────────────

    def test_init_values_zero(self):
        self.assertEqual(self.cov.values.sum(), 0.0)

    def test_init_points_count(self):
        self.assertEqual(len(self.cov.points), 100)

    # ── coverage_ratio ────────────────────────────────────────────────────────

    def test_coverage_ratio_empty(self):
        self.assertEqual(self.cov.coverage_ratio, 0.0)

    def test_coverage_ratio_full(self):
        self.cov.values[:] = 1.0
        self.assertEqual(self.cov.coverage_ratio, 1.0)

    # ── mean_value ────────────────────────────────────────────────────────────

    def test_mean_value_empty(self):
        self.assertEqual(self.cov.mean_value, 0.0)

    def test_mean_value_half(self):
        self.cov.values[:50] = 1.0
        self.assertAlmostEqual(self.cov.mean_value, 0.5, places=4)

    # ── max_gap ───────────────────────────────────────────────────────────────

    def test_max_gap_full_coverage(self):
        self.cov.values[:] = 1.0
        self.assertEqual(self.cov.max_gap, 0.0)

    def test_max_gap_no_coverage(self):
        # Aucun point couvert → trou = 100% du périmètre
        self.assertEqual(self.cov.max_gap, 1.0)


if __name__ == "__main__":
    unittest.main()
