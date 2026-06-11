"""
Tests unitaires — core.components.ComponentStore

4 méthodes testées (push, arr, get/set, __contains__), 2+ cas chacune.
"""

import unittest
import numpy as np
from core.components import ComponentStore
from entities.types import DroneMode


class TestComponentStore(unittest.TestCase):

    def setUp(self):
        self.store = ComponentStore()
        self.store.push({"speed": 10.0, "mode": DroneMode.ACTIVE, "messages": []})
        self.store.push({"speed": 20.0, "mode": DroneMode.ACTIVE, "messages": []})

    # ── push ──────────────────────────────────────────────────────────────────

    def test_push_increments_size(self):
        self.assertEqual(len(self.store.arr("speed")), 2)

    def test_push_backfills_new_field(self):
        # Nouveau champ ajouté au 2e drone → le 1er doit avoir 0 (backfill)
        self.store._n = 0
        s = ComponentStore()
        s.push({"speed": 10.0})
        s.push({"speed": 20.0, "new_field": 5.0})
        self.assertEqual(s.arr("new_field")[0], 0.0)
        self.assertEqual(s.arr("new_field")[1], 5.0)

    # ── arr ───────────────────────────────────────────────────────────────────

    def test_arr_returns_numpy(self):
        self.assertIsInstance(self.store.arr("speed"), np.ndarray)

    def test_arr_values(self):
        np.testing.assert_allclose(self.store.arr("speed"), [10.0, 20.0])

    # ── get / set ─────────────────────────────────────────────────────────────

    def test_get_set_numeric(self):
        self.store.set("speed", 0, 99.0)
        self.assertEqual(self.store.get("speed", 0), 99.0)

    def test_get_set_object(self):
        self.store.set("mode", 1, DroneMode.DEAD)
        self.assertIs(self.store.get("mode", 1), DroneMode.DEAD)

    # ── __contains__ ──────────────────────────────────────────────────────────

    def test_contains_existing_field(self):
        self.assertIn("speed", self.store)
        self.assertIn("mode", self.store)

    def test_contains_missing_field(self):
        self.assertNotIn("inexistant", self.store)


if __name__ == "__main__":
    unittest.main()
