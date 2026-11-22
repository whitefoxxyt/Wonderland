# Wonderland — kit Python

## Installation
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows (macOS / Linux : source .venv/bin/activate)
pip install -e .
```

## Jouer
Écrivez votre algorithme dans la fonction `decide(obs)` de `bot.py`, puis :
```bash
python bot.py --url ws://ADRESSE_DU_SERVEUR:8000 --token VOTRE_TOKEN --level 1
```
- `--mode practice --level N` : entraînement sur un niveau déjà débloqué (gagner le niveau N débloque N+1).
- `--seed 42` : en entraînement, rejoue exactement la même partie (pratique pour débugger).
- `--mode campaign` : les 5 niveaux à la suite. Une mort termine la campagne.

## Règles du protocole
- À chaque tick, le serveur envoie une observation ; votre `decide` doit renvoyer une action :
  `MOVE_UP`, `MOVE_DOWN`, `MOVE_LEFT`, `MOVE_RIGHT`, `ATTACK`, `SHOOT`, `PARRY`, `WAIT`.
- Vous avez un temps limité par tick (annoncé au début de la partie). Trop lent = `WAIT` imposé.
- Une action invalide ou une exception dans `decide` = `WAIT`.
- Se déplacer contre un mur ou un ennemi ne bouge pas, mais **vous tourne** dans cette direction.
