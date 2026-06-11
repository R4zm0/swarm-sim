# systems/movement.py
"""
Steering behaviors — d'après Reynolds (1999), "Steering Behaviors For Autonomous
Characters".

PRINCIPE
────────
On ne téléporte pas le drone vers sa cible : on calcule une FORCE de correction
(steering) qui infléchit progressivement sa vitesse. D'où des trajectoires lisses,
avec inertie — un drone lourd / à faible max_force tourne large (c'est voulu :
ça modélise un planeur vs un FPV nerveux).

CHAÎNE DE CALCUL (par tick)
───────────────────────────
    desired   = direction(pos → target) × vitesse_max        (desired_from_targets)
    steering  = desired − vitesse_actuelle                   (correction à appliquer)
    steering  = clamp(steering, max_force)                   (limite la manœuvrabilité)
    raw_steering = copie de steering    ← AVANT /masse : c'est une FORCE (pour battery)
    accélération = steering / masse                          (2e loi de Newton, F=ma)
    vitesse  += accélération × dt        puis clamp(vitesse, vitesse_max)
    position += vitesse × dt             puis clamp dans le monde

Le clamp par max_force est ce qui empêche un drone de tourner instantanément :
plus max_force est petit devant la vitesse, plus les virages sont larges.

NOTE D'ÉCHELLE (utile pour régler un type de drone)
───────────────────────────────────────────────────
L'autorité en virage dépend du rapport max_force / (mass × vitesse). Si tu
multiplies la vitesse d'un drone par k, multiplie max_force par k² pour garder la
même capacité de virage (sinon il "plane" et coupe les coins).
"""

import numpy as np
from core.world import World


def update(world: World, desired_velocities: np.ndarray, dt: float, ) -> np.ndarray:
    mask       = world.alive_mask
    max_forces = world.max_forces          # fixe par drone (config), vue array
    masses     = world.masses              # fixe par drone (config)
    # Vitesse max EFFECTIVE (dépend batterie + brouillage) → boucle Python par drone,
    # inévitable car effective_speed est une propriété calculée du proxy Drone.
    max_speeds = world.effective_speeds()

    # Force de steering = écart entre vitesse voulue et vitesse actuelle, plafonnée
    # par max_force (la manœuvrabilité physique du drone).
    steering = desired_velocities[mask] - world.velocities[mask]
    steering = _clamp_norm(steering, max_forces[mask])

    # COPIE avant division par la masse : raw_steering reste une force (N = m·a),
    # ce que battery.py attend pour calculer thrust_ratio = ‖force‖ / max_force.
    raw_steering = steering.copy()

    # F = m·a  →  a = F/m. [:, np.newaxis] pour diviser chaque vecteur (2D) par son scalaire.
    steering /= masses[mask, np.newaxis]

    # Intègre l'accélération sur dt, borne la vitesse, puis intègre la position.
    world.velocities[mask] += steering * dt
    world.velocities[mask]  = _clamp_norm(world.velocities[mask], max_speeds[mask])
    world.positions[mask]  += world.velocities[mask] * dt
    # Garde tout le monde dans les limites du monde (évite de sortir de la carte).
    world.positions         = np.clip(world.positions, [0, 0], [world.W, world.H])

    return raw_steering  # consommé par battery.py au même tick


def _clamp_norm(vectors: np.ndarray, max_mag: np.ndarray) -> np.ndarray:
    """
    Plafonne la NORME de chaque vecteur à max_mag, sans changer sa direction.
    scale = 1 si déjà sous la limite, sinon max_mag/‖v‖ (réduction proportionnelle).
    max(‖v‖, 1e-6) évite la division par zéro pour un vecteur nul.
    """
    norms = np.linalg.norm(vectors, axis=1)
    scale = np.where(norms > max_mag, max_mag / np.maximum(norms, 1e-6), 1.0)
    return vectors * scale[:, np.newaxis]


def desired_from_targets(positions: np.ndarray, targets: np.ndarray, max_speeds: np.ndarray) -> np.ndarray:
    """
    Vitesse "désirée" = direction unitaire (pos → target) × vitesse max.
    C'est le vecteur que le drone atteindrait s'il pouvait virer instantanément ;
    le steering ci-dessus l'en approche progressivement.
    """
    directions = targets - positions
    norms = np.linalg.norm(directions, axis=1)
    # Normalise en direction ; max(norm, 1e-6) protège le cas pos == target.
    normalized = directions / np.maximum(norms[:, np.newaxis], 1e-6)
    return normalized * max_speeds[:, np.newaxis]