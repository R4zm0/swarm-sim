# systems/decision.py
"""
Patrouille équidistante du périmètre.
 
Rôle : écrit la cible de chaque drone vivant dans world.targets à chaque
tick. C'est le seul système qui choisit une destination ; movement.py
se charge ensuite d'y aller physiquement.
 
Algorithme : chaque drone a une progression patrol_d, sa position cible en
distance le long du périmètre (0 à P). Sa cible est zone.point_at(patrol_d),
donc toujours exactement sur le polygone. À chaque tick toutes les
progressions avancent du même incrément : l'écart entre drones reste
constant, l'équidistance initiale (P/n) est conservée sans calcul de
répulsion. À la mort d'un drone, les survivants sont ré-espacés une seule
fois (_redistribute), puis l'avance commune reprend.
 
La vitesse d'avance des cibles = coef_Patrouille_vitesse_maxmin (0.75) fois
la vitesse du drone vivant le plus lent. On patrouille en dessous de la
vitesse propre des drones, sinon ils n'ont pas le temps d'atteindre leur
point et prennent les virages trop court. Coef plus haut : ils coupent les
virages ; plus bas : ils rattrapent la cible et tournicotent derrière.
 
Approches écartées : une condition d'arrivée ("avance si le drone est à
moins de X") bloque les drones qui tournent mal — ils dépassent la cible et
orbitent sans jamais la valider. Une cible pilotée par la position réelle
fait converger tous les drones : la cible doit rester une consigne, pas une
mesure.
 
Sans zone : repli en séparation simple type boids (tests sans frontière).
"""
 

import numpy as np
from core.world import World
from entities.types import DroneMode


coef_Patrouille_vitesse_maxmin = 0.75







_last_alive_count = {"n": -1}


# ── Patrouille ────────────────────────────────────────────────────────────────

def _redistribute(world: World, alive_ids: np.ndarray, zone) -> None:
    """
    Ré-espace les patrol_d des SURVIVANTS de façon équidistante.

    Appelée une seule fois quand un drone meurt. Sans elle, les survivants
    garderaient leurs anciennes positions (calculées pour n+1 drones) et
    laisseraient un trou béant là où le mort patrouillait.

    Méthode :
      1. On lit la progression courante de chaque survivant.
      2. On les trie par cette progression → on récupère leur ORDRE réel
         le long du périmètre (qui est devant qui).
      3. On réassigne base + rank * (P/n) : on garde l'ordre mais on impose
         un espacement parfait P/n. 'base' = position du premier survivant,
         pour que la formation ne saute pas brutalement à un autre endroit.
    """
    P        = zone.perimeter
    patrol_d = world.components.arr("patrol_progress")
    n        = len(alive_ids)
    if n == 0:
        return

    # Progressions courantes des survivants, puis ordre le long du périmètre.
    current = patrol_d[alive_ids]
    order   = np.argsort(current)      # indices locaux triés par progression croissante
    base    = current[order[0]]        # ancre = le survivant le plus "en arrière"

    # Réassignation équidistante en conservant l'ordre trouvé.
    for rank, local_idx in enumerate(order):
        drone_id = alive_ids[local_idx]
        patrol_d[drone_id] = (base + rank * P / n) % P


def _patrol(world: World, ctx, zone, dt: float) -> None:
    """Fait glisser toutes les cibles, en redistribuant d'abord si un drone est mort."""
    alive_ids = ctx.alive_ids
    n = len(alive_ids)
    if n == 0:
        return

    # Le nombre de vivants a changé depuis le dernier tick ? → un drone est mort
    # (ou c'est le premier tick). On rééquilibre les positions UNE fois, puis on
    # mémorise le nouveau n pour ne pas redistribuer à chaque tick.
    if n != _last_alive_count["n"]:
        _redistribute(world, alive_ids, zone)
        _last_alive_count["n"] = n

    P        = zone.perimeter
    patrol_d = world.components.arr("patrol_progress")
    
    patrol_speed_min = coef_Patrouille_vitesse_maxmin * float(np.min(world.components.arr("speed")[alive_ids])) #LE GROUPE EST AUSSI FORT QUE SONT PLUS FAIBLE ELEMENTS !

    # Avance commune à tous les vivants → l'écart P/n entre voisins reste constant.
    # Le modulo P referme le périmètre sur lui-même (cyclique).
    patrol_d[alive_ids] = (patrol_d[alive_ids] + patrol_speed_min * dt) % P

    # La cible de chaque drone = le point du périmètre à sa progression.
    # Toujours pile sur une arête → jamais dans une concavité.
    for drone_id in alive_ids:
        world.targets[drone_id] = zone.point_at(patrol_d[drone_id] % P)


# ── Réaction ennemi ───────────────────────────────────────────────────────────

def react_to_enemy(world: World, ctx) -> None:
    """
    Bascule le mode des drones selon le contact ennemi (calculé dans le TickContext).

    EMERGENCY est purement un état visuel/sémantique ici : la navigation ne change
    pas (le drone continue sa patrouille), seul l'affichage le passe en rouge.
    On repasse en ACTIVE dès que le contact est perdu — mais on ne TOUCHE PAS aux
    morts : is_alive est False pour DEAD, et un mort n'est pas dans ctx.alive_ids,
    donc il ne peut pas être réveillé ici.
    """
    for local_i, drone_id in enumerate(ctx.alive_ids):
        if ctx.enemy_contact[local_i]:
            world.components.set("mode", drone_id, DroneMode.EMERGENCY)
        elif world.components.get("mode", drone_id) is DroneMode.EMERGENCY:
            world.components.set("mode", drone_id, DroneMode.ACTIVE)


# ── Update principal ──────────────────────────────────────────────────────────

def update(world: World, ctx, zone=None, dt: float = 1/60) -> None:
    """
    Point d'entrée appelé par le scheduler à chaque tick.

    - Avec une zone  : patrouille de périmètre (le mode normal de la sim).
    - Sans zone      : fallback de séparation pure (essaim libre, type boids),
                       utile pour tester le mouvement sans frontière définie.
    """
    alive_ids = ctx.alive_ids
    if len(alive_ids) == 0:
        return

    react_to_enemy(world, ctx)

    if zone is not None:
        _patrol(world, ctx, zone, dt)
    else:
        # ── Fallback sans zone : séparation inverse-carré (anti-collision) ────
        # Chaque drone est repoussé par ses voisins alliés détectés. Force ∝ 1/d²
        # (répulsion forte de près, faible de loin), puis normalisée en direction.
        positions = world.positions[alive_ids]
        ally_mask = ctx.detected & ctx.friendly
        # Distance "sûre" : inf là où il n'y a pas d'allié détecté → poids nul,
        # et on exclut d == 0 (soi-même) pour ne pas diviser par zéro.
        safe_dist = np.where(ally_mask & (ctx.distances > 0), ctx.distances, np.inf)
        weights   = 1.0 / safe_dist ** 2
        # Somme pondérée des vecteurs (i → j) ; ctx.diff[i,j] = pos[i] - pos[j].
        forces    = np.sum(ctx.diff * weights[:, :, np.newaxis], axis=1)
        norms     = np.linalg.norm(forces, axis=1, keepdims=True)
        sep       = np.where(norms > 1e-6, forces / norms, 0.0)
        # Cible = un peu "devant" dans la direction de fuite (500 u), puis clamp monde.
        world.targets[alive_ids] = positions + sep * 500.0
        world.targets = np.clip(world.targets, [0, 0], [world.W, world.H])