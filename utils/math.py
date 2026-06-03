# utils/math.py  — une fonction réutilisable
import numpy as np

def clamp_to_world(position: np.ndarray, world_w: float, world_h: float) -> np.ndarray:
    return np.clip(position, [0.0, 0.0], [world_w, world_h])
