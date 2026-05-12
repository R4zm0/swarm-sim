# core/config_loader.py
#pour l'instant ça charge juste mes configs de drones
#update : la maps des niveaux à reco

import json
from pathlib import Path

def load_drone_configs():
    path = Path(__file__).resolve().parent.parent.parent / "config" / "drones.json"

    with open(path, "r") as f:
        return json.load(f)
    # test
