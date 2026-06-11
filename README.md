# swarm-sim

Simulateur d'essaim de drones pour la patrouille de périmètre.
Jumeau numérique configurable : drones, zone de mission et stratégie de
décision sont des données JSON, pas du code.

## Lancer

```bash
pip install -r requirements.txt
python main.py
```

Sélectionnez un scénario dans l'écran de mission, puis DÉMARRER.
Contrôles en simulation : molette = zoom, clic droit = déplacement,
espace = pause, flèche = pas-à-pas, S = sauvegarder, L = charger, D = debug.

## Tests

```bash
python -m unittest discover tests
```

ou double-clic sur `run_tests.py` (29 tests).

## Architecture

Voir `ARCHITECTURE.md` : organisation des packages, philosophie orientée
données, pipeline d'un pas de simulation, conventions.
