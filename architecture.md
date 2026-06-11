# swarm-sim — Architecture

Simulateur d'essaim de drones pour la patrouille de périmètre. Conçu comme un
jumeau numérique : drones, géométrie de mission et stratégie de décision sont
des données configurables (JSON), pas du code.

## Philosophie : orienté données (pseudo-ECS)

L'état des drones ne vit pas dans des objets : il vit dans des tableaux numpy
centraux, un tableau par attribut (Struct-of-Arrays), transformés à chaque pas
par des systèmes vectorisés. Un "type de drone" est un motif dans les données,
pas une classe.

- **Entité** : un drone = un identifiant entier (un indice de ligne).
- **Composant** : un attribut par-drone (speed, battery_level, mode...),
  stocké pour tous les drones dans `ComponentStore` (`core/components.py`).
  Les numériques sont des arrays numpy, le reste (str, enum, list) des listes.
- **Système** : une fonction pure qui transforme ces tableaux
  (`systems/*.py`). Pas de classes, pas d'état caché : testable et
  interchangeable par simple changement d'import.

La classe `Drone` (`entities/drone.py`) existe comme **proxy** : elle ne
stocke rien, `drone.battery_level` lit/écrit directement dans le tableau
central via `__getattr__`/`__setattr__`. Elle héberge aussi la logique
individuelle polymorphe : les courbes de décharge batterie sont ses méthodes,
injectées une fois à la construction selon `battery_model` (Strategy).

**Règle d'or : ajouter un champ à tous les drones = un champ dans
`drones.json` + une ligne dans `schemas.py`. Rien d'autre.** Le
ComponentStore se peuple automatiquement depuis la config validée.

## Arborescence

```
swarm-sim/
├── main.py                  Point d'entrée : sélection de mission, threads sim + UI
├── core/
│   ├── world.py             Conteneur central : positions/velocities/targets (N,2),
│   │                        alive_mask, ComponentStore, drones, ennemis fixes
│   ├── components.py        ComponentStore : registre {nom → array(N)} par-drone
│   ├── scheduler.py         Scheduler + TickContext : pipeline d'un tick
│   ├── schemas.py           DroneConfig (Pydantic) : validation des configs
│   ├── config_loader.py     Chargement drones.json, héritage récursif par "parent"
│   ├── scenario_loader.py   Chargement d'un scénario : zone, drones, ennemis
│   ├── save_load.py         Sauvegarde/restauration d'une mission (JSON)
│   └── config/
│       └── drones.json      Types de drones, héritage par "parent", guide de tuning
├── entities/
│   ├── drone.py             Proxy : vue objet sur les tableaux du World
│   └── types.py             DroneMode : ACTIVE, EMERGENCY, DEAD
├── systems/                 Fonctions pures appelées par le scheduler
│   ├── decision.py          Patrouille équidistante (consigne glissante + redistribution)
│   ├── decision_extra.py    Variante essaim hétérogène (gaps pondérés vitesse×rayon)
│   ├── movement.py          Steering behaviors (Reynolds) : forces, inertie, intégration
│   ├── battery.py           Drain ∝ effort de manœuvre, passage DEAD sous 20 %
│   ├── detection.py         Matrices NxN qui-voit-qui / ami-ennemi
│   └── coverage.py          CoverageMap : métrique de couverture du périmètre
├── environment/
│   └── zone.py              PatrolZone : polygone, abscisse curviligne, point_at
├── utils/
│   ├── math.py              clamp_to_world
│   └── spatial.py           distance_matrix (broadcasting numpy)
├── visualization/           Interface pygame (dépend de la sim, jamais l'inverse)
│   ├── renderer.py          Boucle de rendu : caméra, HUD, playback, debug
│   ├── mission_select.py    Écran de lancement : scénarios et sauvegardes
│   ├── save_panel.py        Panneaux save (S) / load (L), classe mère _BasePanel
│   └── utils.py             Projection monde→pixels, cache de sprites
├── tests/                   29 tests unitaires (unittest)
│   ├── test_zone.py         PatrolZone : perimeter, point_at, contains, waypoints
│   ├── test_components.py   ComponentStore : push, arr, get/set, backfill
│   ├── test_coverage.py     CoverageMap : ratio, mean, max_gap
│   └── test_math.py         clamp_to_world
└── data/
    ├── scenarios/           Missions (JSON) : zone, drones, ennemis, fond de carte
    ├── saves/<scénario>/    Sauvegardes de mission, rangées par scénario
    ├── maps/                Fonds de carte (PNG)
    └── sprites/             Sprites de drones (PNG), champ "sprite" des configs
```

## Le tick (core/scheduler.py)

Pipeline fixe, chaque étape consomme la sortie de la précédente :

```
ctx = TickContext(world)    précalculs : alive_ids, matrice de distances,
                            détection drone/drone, contact ennemis
1. decision.update()        écrit world.targets (le cerveau)
2. movement.update()        steering → intègre vitesses et positions,
                            retourne raw_steering (force avant /masse)
3. battery.update()         drain ∝ ||raw_steering||/max_force, morts
4. coverage.update()        marque les points du périmètre vus
5. _sync_alive_mask()       acte les morts pour le tick suivant
```

Un drone mort à l'étape 3 reste compté jusqu'à la fin du tick (cohérence des
indices) et disparaît au tick suivant, ce qui déclenche la redistribution
dans decision.

## Données et configuration

- `drones.json` : un bloc par type. Héritage par champ `parent`, résolu
  récursivement avec détection de cycles (`config_loader._resolve`). Les
  blocs préfixés `_` sont ignorés au chargement (documentation embarquée).
  Validation Pydantic en sortie (`schemas.DroneConfig`).
- Scénarios : zone (sommets du polygone), drones engagés (tout champ
  numérique surchageable par drone), ennemis, fond de carte, paramètres de
  couverture.
- Sauvegardes : état mutable uniquement (frozenset MUTABLE du
  ComponentStore) ; la config est rechargée depuis sa source. Enums
  sérialisés par leur nom. Une sauvegarde n'est rechargeable que dans son
  scénario d'origine.

## Conventions

- L'affichage dépend de la simulation, jamais l'inverse : la sim tourne
  headless (tests, futur RL).
- Les systèmes prennent (world, ctx, ...) et n'écrivent que dans les
  tableaux du World.
- Vectoriser les calculs uniformes sur N drones ; réserver le proxy aux
  comportements individuels, rares ou polymorphes.
- La sim tourne dans son thread (60 ticks/s), l'UI envoie ses commandes via
  le dict partagé sim_state {paused, speed, step}.

## Lancer

```
pip install -r requirements.txt
python main.py              # sélection de mission puis simulation
python -m unittest discover tests    # ou run_tests.py
```
