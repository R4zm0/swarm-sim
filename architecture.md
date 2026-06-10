# swarm-sim

Drone swarm simulation framework.

## Structure

- `core/` — world, config, scheduler
- `entities/` — drone model and type definitions
- `systems/` — movement, coverage, comms, EW, decision
- `environment/` — grid, terrain, weather, jamming
- `utils/` — math and spatial helpers
- `visualization/` — renderer
- `data/scenarios/` — scenario JSON files
- `data/logs/` — simulation output logs

## Usage

```bash
pip install -r requirements.txt
python main.py
```


# A FAIRE CODER LE DEBUT DU DRONE DANS LA CLASSE QUI VA BIEN! !!!
# FAIRE UN JSON BASE STAT POUR SUPPORTER A l'AVENIR LES CHANGEMENT DE STATS  