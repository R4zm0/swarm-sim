from enum import Enum, auto

class DroneMode(Enum):
    ACTIVE          = auto()
    EMERGENCY       = auto()
    DEAD            = auto()

class DroneRole(Enum):
    SCOUT   = auto()
    CARRIER = auto()
    RELAY   = auto()
