
"""Schéma fonctionnes pour les configuration de drones, chargées depuis JSON.

Le but est d'avoir une validation stricte des données, avec des valeurs par défaut et des contraintes (ex: speed > 0).

pour cela on utilise Pydantic, qui est une bibliothèque de validation de données très populaire en Python. 

C'est le Standard dans l'industrie type jeu vidéo et pipeline de donnée, celà nous évitera de faire des validations manuelles à chaque fois qu'on charge une config, et ça rendra le code plus robuste et maintenable

dans l'implémentation de nouvelles fonctionalités, on pourra facilement ajouter de nouveaux champs à ce schéma, avec des contraintes spécifiques, sans avoir à toucher au code de chargement ou d'utilisation des configs ailleurs dans le projet.

et l'implémentations de nouvelles fonctions, on réduit l'erreur au futur et on s'évite plein de test à chaque implémentaiton de fonctions.
"""

from pydantic import BaseModel, Field
from entities.types import DroneRole

class DroneConfig(BaseModel):
    role:             DroneRole = DroneRole.SCOUT
    speed:            float     = Field(10.0,  gt=0)
    sensor_radius:    float     = Field(50.0,  gt=0)
    comm_radius:      float     = Field(150.0, gt=0)
    battery_capacity: float     = Field(16.8, gt=0)
    max_force:        float     = Field(5.0,   gt=0)
    mass:             float     = Field(1.0,   gt=0)
    