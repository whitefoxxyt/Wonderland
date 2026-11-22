# Wonderland — kit TypeScript / Angular

Écrivez votre algorithme dans **`src/bot.ts`** (fonction `decide(obs)`). Le reste est fourni.

```
src/types.ts       types de l'observation et des messages (lisez-le : c'est la doc du jeu)
src/client.ts      connexion au serveur (ne pas modifier)
src/bot.ts         VOTRE ALGORITHME
src/run-node.ts    lancer le bot depuis un terminal
angular/           service + composant prêts à copier dans un projet Angular
```

## Option 1 : en terminal (le plus simple pour itérer)
Node.js 22.18 ou plus récent exécute directement les fichiers `.ts` :
```bash
node src/run-node.ts --url ws://ADRESSE_DU_SERVEUR:8000 --token VOTRE_TOKEN --level 1
```
- `--level N` : entraînement sur un niveau déjà débloqué (gagner le niveau N débloque N+1).
- `--seed 42` : en entraînement, rejoue exactement la même partie (pratique pour débugger).
- `--mode campaign` : les 5 niveaux à la suite. Une mort termine la campagne.

## Option 2 : dans une application Angular
1. `ng new wonderland-bot` (Angular 17 ou plus récent).
2. Copiez `src/types.ts`, `src/client.ts` et `src/bot.ts` dans `src/sdk/`,
   et le contenu de `angular/` dans `src/app/`.
3. Ajoutez `<app-bot-runner />` dans `app.component.html` (et `BotRunnerComponent` dans ses `imports`).
4. `ng serve`, puis renseignez l'adresse du serveur et votre token dans le formulaire.

## Règles du protocole
- À chaque tick, `decide` reçoit l'observation et renvoie une action :
  `MOVE_UP`, `MOVE_DOWN`, `MOVE_LEFT`, `MOVE_RIGHT`, `ATTACK`, `SHOOT`, `PARRY`, `WAIT`.
- Temps de réponse limité (annoncé au début de la partie) : trop lent = `WAIT` imposé.
- Une action invalide ou une exception dans `decide` = `WAIT`.
- Se déplacer contre un mur ou un ennemi ne bouge pas, mais **vous tourne** dans cette direction.
