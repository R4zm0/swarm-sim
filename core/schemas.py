"""
Schémas Pydantic pour la validation des configs de drones chargées depuis JSON.
Toute modification du JSON drones.json doit être reflétée ici.
"""

from pydantic import BaseModel, Field


class DroneConfig(BaseModel):
    type:             str   = Field(..., description="identifiant de type, ex: fpv, isr, loitering")
    display_name:     str   = Field(..., description="nom d'affichage pour les logs et l'interface")

    speed:            float = Field(10.0,  gt=0)
    sensor_radius:    float = Field(50.0,  gt=0)
    comm_radius:      float = Field(150.0, gt=0)
    battery_capacity: float = Field(100.0, gt=0)
    max_force:        float = Field(10.0,  gt=0)
    mass:             float = Field(1.0,   gt=0)

    # Modèle batterie
    battery_model:     str   = Field("lipo")
    battery_knee:      float = Field(0.20, ge=0.0, le=1.0)
    battery_steepness: float = Field(15.0, gt=0)
    power_idle:        float = Field(0.001, ge=0.0)
    power_max_steer:   float = Field(0.005, ge=0.0)

    # Sprite custom (optionnel, fichier dans data/sprites/)
    sprite: str | None = Field(None, description="nom du fichier sprite dans data/sprites/")