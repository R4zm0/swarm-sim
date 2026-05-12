from enum import Enum, auto

class DroneMode(Enum):
    IDLE            = auto()
    PATROLLING      = auto()
    MOVING          = auto()
    SCANNING        = auto()
    RETURNING       = auto()
    EMERGENCY       = auto()
    DEAD            = auto()

class DroneRole(Enum):
    SCOUT   = auto()
    CARRIER = auto()
    RELAY   = auto()
