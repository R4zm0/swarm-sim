# core/components.py
"""
ComponentStore — registre générique de composants par-drone.

Philosophie :
    Array-of-Structs → Struct-of-Arrays.
    Chaque scalaire (speed, battery_level...) est un numpy array (N,).
    Les types non-numériques (str, DroneMode, list) sont des listes Python.

Ajouter un champ à la sim = JSON + schemas.py seulement.
    ComponentStore se peuple depuis DroneConfig.model_dump() — aucune
    déclaration manuelle dans World ou Drone.

Save/load :
    state_dict()   → dict sérialisable des composants mutables (état mission)
    load_state()   → restore depuis un state_dict
"""

import copy
import numpy as np


class ComponentStore:

    # Composants mutables — seront inclus dans save/load de mission
    MUTABLE: frozenset[str] = frozenset({
        "battery_level",
        "jamming_level",
        "signal_quality",
        "sensor_efficiency",
        "mode",
        "messages",
        "patrol_progress",
    })

    def __init__(self) -> None:
        self._floats:  dict[str, np.ndarray] = {}   # scalaires float  (N,)
        self._objects: dict[str, list]       = {}   # strings, enums, lists
        self._n = 0

    # ── Ajout d'un drone ──────────────────────────────────────────────────────

    def push(self, data: dict) -> None:
        """
        Enregistre un nouveau drone avec toutes ses valeurs initiales.
        data = config.model_dump() + état initial — tous les champs d'un coup.
        Crée le container au premier push si le champ n'existe pas encore.
        """
        for key, value in data.items():
            if self._is_numeric(value):
                if key not in self._floats:
                    # Backfill : les drones précédents ont 0 pour ce nouveau champ
                    self._floats[key] = np.zeros(self._n, dtype=float)
                self._floats[key] = np.append(self._floats[key], float(value))
            else:
                if key not in self._objects:
                    self._objects[key] = [None] * self._n
                v = copy.copy(value) if isinstance(value, list) else value
                self._objects[key].append(v)
        self._n += 1

    @staticmethod
    def _is_numeric(value) -> bool:
        """float et int, mais pas bool (bool est sous-classe de int en Python)."""
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    # ── Accès ─────────────────────────────────────────────────────────────────

    def arr(self, name: str) -> np.ndarray:
        """Array complet (N,) — pour les systèmes vectorisés (movement, battery...)."""
        return self._floats[name]

    def get(self, name: str, i: int):
        """Valeur d'un drone i — utilisé par le proxy Drone."""
        if name in self._floats:
            return float(self._floats[name][i])
        return self._objects[name][i]

    def set(self, name: str, i: int, value) -> None:
        """Écrit la valeur d'un drone i — utilisé par le proxy Drone."""
        if name in self._floats:
            self._floats[name][i] = float(value)
        else:
            self._objects[name][i] = value

    def __contains__(self, name: str) -> bool:
        return name in self._floats or name in self._objects

    # ── Save / Load ───────────────────────────────────────────────────────────

    def state_dict(self) -> dict:
        """
        Sérialise uniquement les composants mutables (état de mission).
        Config immuable (speed, mass...) non incluse — rechargée depuis JSON au load.
        Les enums (DroneMode) sont convertis en string pour la sérialisation JSON.
        """
        result = {}
        for name in self.MUTABLE:
            if name in self._floats:
                result[name] = self._floats[name].tolist()
            elif name in self._objects:
                # Convertit les enums en string pour JSON
                result[name] = [
                    v.name if hasattr(v, "name") and hasattr(v, "value") else v
                    for v in self._objects[name]
                ]
        return result

    def load_state(self, state: dict) -> None:
        """
        Restore depuis un state_dict.
        Reconvertit les strings en enums si nécessaire.
        """
        from entities.types import DroneMode
        for name, values in state.items():
            if name in self._floats:
                self._floats[name] = np.array(values, dtype=float)
            elif name in self._objects:
                if name == "mode":
                    self._objects[name] = [
                        DroneMode[v] if isinstance(v, str) else v
                        for v in values
                    ]
                else:
                    self._objects[name] = list(values)