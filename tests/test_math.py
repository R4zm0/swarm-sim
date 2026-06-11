"""
Tests unitaires — utils.math.clamp_to_world

1 fonction, 4 cas (les 4 quadrants de dépassement + cas interne).
"""

import unittest
import numpy as np
from utils.math import clamp_to_world


class TestClampToWorld(unittest.TestCase):

    W, H = 1000.0, 500.0

    def test_inside_unchanged(self):
        p = clamp_to_world(np.array([100.0, 200.0]), self.W, self.H)
        np.testing.assert_allclose(p, [100.0, 200.0])

    def test_clamps_negative(self):
        p = clamp_to_world(np.array([-50.0, -10.0]), self.W, self.H)
        np.testing.assert_allclose(p, [0.0, 0.0])

    def test_clamps_above_max(self):
        p = clamp_to_world(np.array([2000.0, 800.0]), self.W, self.H)
        np.testing.assert_allclose(p, [self.W, self.H])

    def test_clamps_mixed(self):
        p = clamp_to_world(np.array([-10.0, 800.0]), self.W, self.H)
        np.testing.assert_allclose(p, [0.0, self.H])


if __name__ == "__main__":
    unittest.main()
