# core/config_loader.py
#pour l'instant ça charge juste mes configs de drones
#update : la maps des niveaux à reco

# core/config_loader.py
import json
from pathlib import Path
from core.schemas import DroneConfig

def _resolve(name: str, raw: dict) -> dict:
    """Remonte récursivement la chaîne parent / enfant, s'arrête quand il n'y a plus de parent, et fusionne les configs (l'enfant écrase le parent)"""
    
    entry = raw[name].copy()
    parent_name = entry.pop("parent", None)

    if parent_name:
        parent = _resolve(parent_name, raw)
        return {**parent, **entry}   # l'enfant écrase le parent
    return entry

def load_drone_configs() -> dict[str, DroneConfig]:
    """import toutes les configs de drones depuis le JSON, et les valide via Pydantic (DroneConfig) """

    path = Path(__file__).resolve().parent.parent.parent / "config" / "drones.json"

    with open(path, "r") as f:
        raw = json.load(f)

    return {
        name: DroneConfig(**_resolve(name, raw))
        for name in raw
        if not name.startswith("_")   # ignore _base et autres meta
    }