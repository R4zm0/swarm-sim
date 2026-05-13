from enum import Enum, auto

class DroneMode(Enum):
    ACTIVE          = auto()
    EMERGENCY       = auto()
    DEAD            = auto()