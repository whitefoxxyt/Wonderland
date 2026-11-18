# Wonderland Code — Architecture du back (moteur Python)

> Jeu de programmation : les équipes codent un bot qui traverse 5 niveaux inspirés d'*Alice au pays des merveilles*.
> Aucune action manuelle : seul l'algorithme joue.
> Contraintes : 5 équipes × 3 joueurs, 5 bots max en simultané, événement de ~2 h, en décembre.

---

## 1. Décision structurante : où tourne le code des joueurs ?

| Option | Principe | + | − |
|---|---|---|---|
| **A. Bot client (recommandé)** | Le bot tourne chez l'équipe (projet Python ou Angular prébuild), se connecte en WebSocket au back, reçoit une observation à chaque tick et renvoie une action. | Agnostique du langage (Python **et** TypeScript), aucun code étranger exécuté sur ton serveur, debug facile pour les joueurs (print, breakpoints). | Il faut empêcher le jeu « à la main » (voir §1.1). |
| B. Upload de code | L'équipe envoie un `.py`, le serveur l'exécute dans un sous-processus isolé. | Contrôle total, rejouable. | Sandbox à sécuriser, impossible pour les joueurs Angular sans runtime Node, debug pénible. |

**Recommandation : A**, avec en bonus un *upload du code final* en fin d'événement pour vérification par le jury.

### 1.1 Empêcher le jeu manuel
- **Timeout par tick** (ex. 300 ms, configurable par niveau) : pas de réponse → action `WAIT` imposée. Impossible de suivre un niveau de 300+ ticks à la main.
- **Pas de pause** : la partie avance dès que le bot répond ou que le timeout expire.
- **Brouillard + infos uniquement en JSON** : l'observation est un objet structuré, pas une image ; un humain ne peut pas l'exploiter assez vite.
- **Audit** : le serveur logge la latence de réponse par tick ; une latence « humaine » (≈ 150–300 ms très variable sur tous les ticks) est visible sur le dashboard admin.

---

## 2. Vue d'ensemble

```
┌──────────────┐  WS /ws/bot   ┌────────────────────────── BACK (FastAPI, 1 process asyncio) ─────────────────────────┐
│ Bot équipe 1 │──────────────▶│  BotGateway ──▶ RunManager ──▶ Run (asyncio.Task) ──▶ Engine.step()                   │
│ (Py / TS)    │◀──────────────│                    │                                     │ events                      │
└──────────────┘               │                    │                                     ▼                             │
       …  ×5                   │                    │                    EventBus ──┬──▶ AchievementService             │
                               │                    │                               ├──▶ ScoringService                 │
┌──────────────┐  WS /ws/live  │                    │                               ├──▶ ReplayRecorder               │
│ Écran public │◀──────────────│  BroadcastHub ◀────┴───────────────────────────────┘                                 │
│  (Angular)   │               │                                                                                       │
└──────────────┘  REST /api    │  Persistence (SQLite / SQLModel) : teams, runs, scores, achievements, replays         │
                               └───────────────────────────────────────────────────────────────────────────────────────┘
```

**Principe clé : le moteur est pur et déterministe.** `Engine.step(state, action) -> (state, events)` ne fait aucune I/O, n'utilise que son RNG seedé. Tout le reste (succès, score, diffusion, replays) **écoute les événements** émis par le moteur. Conséquences :
- testable unitairement sans réseau ;
- un replay = `seed + liste d'actions` → re-simulable à l'identique ;
- ajouter un succès = ajouter un listener, sans toucher au moteur.

---

## 3. Découpage des modules

```
backend/
├── app/
│   ├── main.py                  # FastAPI, montage des routes, lifespan
│   ├── config.py                # tick timeout, limites, chemins (pydantic-settings)
│   │
│   ├── engine/                  # ⚙️ CŒUR — zéro dépendance réseau/DB
│   │   ├── grid.py              # Grid, Tile (WALL, FLOOR, TRAP, DOOR, EXIT, MIST…)
│   │   ├── entities.py          # Entity, Player, Mob, Boss, Projectile, Item
│   │   ├── actions.py           # Enum Action + validation
│   │   ├── state.py             # GameState (immuable ou copiable), snapshot()
│   │   ├── simulation.py        # Engine.step() : ordre de résolution du tick
│   │   ├── systems/             # un fichier par règle
│   │   │   ├── movement.py
│   │   │   ├── combat.py        # attaque, parade, dégâts, knockback
│   │   │   ├── projectiles.py
│   │   │   ├── traps.py
│   │   │   └── pickups.py       # chapeaux, armes, potions
│   │   ├── ai/                  # comportements des mobs
│   │   │   ├── base.py          # MobBrain.decide(state, mob) -> Action
│   │   │   ├── patrol.py, chaser.py, ranged.py, guard.py
│   │   │   └── queen.py         # machine à états du boss
│   │   ├── observation.py       # ce que le bot voit (brouillard, rayon de vision)
│   │   ├── events.py            # dataclasses d'événements
│   │   └── rng.py               # Random seedé par run
│   │
│   ├── levels/
│   │   ├── loader.py            # Tiled JSON / ASCII -> GameState initial
│   │   └── data/                # level1.json … level5.json (+ variantes)
│   │
│   ├── runs/
│   │   ├── manager.py           # RunManager : file, quotas, concurrence
│   │   ├── run.py               # boucle d'un run (await bot, step, publish)
│   │   └── bot_gateway.py       # protocole WS bot, auth par token d'équipe
│   │
│   ├── achievements/
│   │   ├── base.py              # Achievement(id, hidden, hint, on_event, check)
│   │   ├── definitions.py       # les ~15 succès
│   │   └── service.py           # état persistant par équipe (cross-runs)
│   │
│   ├── scoring/
│   │   ├── service.py           # score par run + classement
│   │   └── formulas.py
│   │
│   ├── broadcast/
│   │   ├── hub.py               # pub/sub spectateurs, sélection du run « vedette »
│   │   └── featured.py          # règle de priorité
│   │
│   ├── replays/recorder.py      # seed + actions + events compressés
│   ├── persistence/             # models.py (SQLModel), repo.py
│   └── api/                     # routes REST + WS
│       ├── teams.py, runs.py, leaderboard.py, achievements.py, admin.py
│       └── ws.py                # /ws/bot, /ws/live, /ws/live/{run_id}
└── tests/
    ├── engine/                  # tests de règles (déplacement, parade, pièges…)
    ├── levels/                  # chaque niveau est faisable (bot de référence)
    └── achievements/
```

**Stack proposée** : Python 3.12+ · FastAPI + Uvicorn (WebSocket natif) · Pydantic v2 (schémas du protocole, partagés en JSON Schema avec les SDK) · SQLModel + SQLite · pytest. Pas de Redis/Celery : 5 runs simultanés sur un tick de quelques ms, un seul process asyncio suffit largement.

---

## 4. Le moteur

### 4.1 Boucle de tick (ordre de résolution déterministe)
1. Lecture de l'action du joueur (ou `WAIT` si timeout / invalide → événement `InvalidAction`).
2. **Parade** : activée en premier (dure ce tick).
3. **Déplacement / attaque du joueur**.
4. **Décisions des mobs** (`MobBrain.decide`) puis résolution dans l'ordre de leur `id`.
5. **Projectiles** avancent, collisions.
6. **Pièges** (déclenchement, cooldowns), **brouillard** mis à jour.
7. **Ramassage** d'objets, **morts**, conditions de **fin de niveau**.
8. `tick += 1`, émission des événements, construction de l'observation.

### 4.2 Actions
```
MOVE_UP | MOVE_DOWN | MOVE_LEFT | MOVE_RIGHT
ATTACK              # au corps-à-corps, dans la direction regardée (couteau)
SHOOT               # arme à distance, dans la direction regardée (munitions/cooldown)
PARRY               # bloque une attaque frontale ce tick ; parade parfaite = étourdit l'ennemi
TURN_<DIR>          # (option) se tourner sans bouger, utile pour viser
WAIT
USE                 # (option) potion, levier, porte
```
Proposition : **la parade n'est utile qu'avec du timing**. Les ennemis *télégraphient* leur attaque (état `WINDUP` visible dans l'observation 1 tick avant). Parer pendant le tick de frappe → `PerfectParry` (étourdit 2 ticks). Ça transforme le combat en vrai problème algorithmique (lire l'état, anticiper) au lieu de spammer ATTACK.

### 4.3 Armes (dans l'esprit Alice, design original)
- **Couteau à beurre** (départ) : 1 case, 1 dégât, pas de cooldown.
- **Lance-sucres du Chapelier** (récupéré fin niveau 2) : projectile en ligne droite, portée 6, 1 dégât, cooldown 3 ticks, rebondit sur les murs ? (option niveau 4).
- Option : **Montre à gousset** du Lapin (objet) : ralentit les mobs 5 ticks, 1 utilisation par niveau.

### 4.4 Observation envoyée au bot
```json
{
  "tick": 42, "level": 3, "time_left": null,
  "you": {"x": 4, "y": 7, "hp": 3, "max_hp": 5, "facing": "UP",
          "weapon": "knife", "ammo": 0, "cooldowns": {"shoot": 0}},
  "vision_radius": 3,
  "grid": [["#", ".", "?", "..."]],           // "?" = case inconnue (brouillard)
  "entities": [
    {"id": 12, "type": "card_guard", "x": 5, "y": 7, "hp": 2, "state": "WINDUP", "facing": "LEFT"}
  ],
  "items": [{"type": "hat", "x": 1, "y": 2}],
  "events_last_tick": ["DamageTaken", "TrapTriggered"]
}
```
Le SDK fournit des helpers : `obs.neighbors()`, `obs.find("exit")`, `obs.is_walkable(x,y)`… mais **pas** de pathfinding (c'est le travail des joueurs au niveau 3).

### 4.5 Morts — ✅ décidé : la mort termine le run
Mourir **met fin au run** (statut `DEAD`, événement `PlayerDied(level, cause)`). Un run se termine donc quand : niveau 5 gagné, mort, abandon/déconnexion, ou dépassement de la limite dure de ticks par niveau (ex. 2000, statut `TIMEOUT`).
Conséquences :
- en **practice**, on relance directement le niveau voulu (cooldown court, ex. 3 s) ;
- en **campagne**, une mort oblige à repartir du niveau 1 → c'est ce qui donne sa valeur au classement « campagne » ;
- le succès *Plus mort que vif* se fait naturellement en practice (cumul équipe sur tous les runs).

---

## 5. Niveaux

### 5.1 Format
**Recommandation : [Tiled](https://www.mapeditor.org/) (export JSON)**. Le même fichier sert au back (logique) et au front Angular (pixel art), avec des calques :
- `terrain` (tiles : mur, sol, eau, brume, porte, sortie)
- `objects` (spawns : joueur, mobs avec propriétés `brain=patrol`, `path=…`, chapeaux, pièges avec `period=4`)

Fallback rapide pour prototyper : ASCII + YAML.
```
####################
#S....#.......H....#
#.###.#.####.####..#
#...G.......T....E.#
####################
```
La grille est de taille libre dans le moteur ; 20×20 par défaut, 30×30 envisageable pour les niveaux 4–5 (le front gère une caméra).

### 5.2 Les 5 niveaux (proposition de thème + compétence)

| # | Thème | Compétence algo | Mécaniques |
|---|---|---|---|
| 1 | **Le terrier du Lapin Blanc** | Déplacements, lecture de grille | Couloirs, portes, une clé. Secret : potion « Bois-moi » + petite porte → raccourci & chapeau. Vision totale. |
| 2 | **Le thé du Chapelier fou** | Premiers combats, gestion des PV | Loirs (lents), Lièvres de mars (rapides, erratiques). Télégraphe d'attaque. Récompense : lance-sucres. |
| 3 | **La forêt brumeuse** | Pathfinding sous information partielle, exploration | Vision rayon 3, pièges cachés révélés à 1 case, chemins qui se referment. La Chenille donne un indice si on `WAIT` 3 ticks à côté d'elle. Chat du Cheshire caché. |
| 4 | **Le labyrinthe de haies de la Reine** | Pathfinding + timing (pièges périodiques) + combat | Pièges à cycles (actifs 1 tick sur 4), gardes-cartes en patrouille, roses blanches à « peindre » (attaquer). |
| 5 | **Le croquet de la Reine de Cœur** | Lire une machine à états, exploiter l'environnement | Boss multi-phases (§5.3), hérissons-pièges au sol réutilisables contre elle. |

### 5.3 Boss : la Reine de Cœur
Machine à états lisible dans l'observation (`state`) :
- **Phase 1 – « Qu'on lui coupe la tête ! »** : invoque 2 gardes-cartes toutes les 15 ticks.
- **Phase 2 (< 60 % PV) – Croquet** : lance des hérissons en ligne (projectiles parables), charge en ligne droite.
- **Phase 3 (< 25 % PV) – Rage** : charges plus fréquentes, mais **elle s'étourdit si elle charge dans un pilier / déclenche un piège au sol**.
- Les pièges au sol (dalles piégées) blessent **toutes** les entités → permet le succès « vaincre sans la toucher ».

---

## 6. Gestion des runs et de la charge

### 6.1 Modèle
- **Team** : `id, name, token` (token donné aux équipes, à mettre dans la config du SDK).
- **Run** : `id, team_id, mode (practice|campaign), level_start, seed, status, started_at, ended_at, ticks, deaths, score`.
- Deux modes :
  - **Practice** : n'importe quel niveau déjà débloqué, rejouable à volonté. Débloque des succès « par niveau ».
  - **Campaign** : du niveau 1 au 5 enchaînés ; seul mode éligible au succès *15 min* et au classement final.

### 6.2 RunManager (charge)
- ✅ décidé : **1 run practice + 1 run campagne** actifs par équipe ⇒ max **10 runs** en parallèle. Lancer un 2ᵉ run du même mode coupe le précédent.
- Chaque run = une `asyncio.Task`. Le coût CPU d'un tick est négligeable ; le goulot est la latence réseau du bot.
- **Cooldown** entre deux runs d'une équipe (ex. 10 s) pour éviter le spam.
- Limite globale `MAX_CONCURRENT_RUNS = 10` avec file d'attente (sécurité si on ajoute des équipes).
- La diffusion vedette ne considère **que les runs campagne** par défaut (les practice restent visibles en mosaïque).
- Kill-switch admin : `POST /api/admin/runs/{id}/stop`, `POST /api/admin/freeze` (fige tous les runs, ex. pour l'annonce du gagnant).

### 6.3 Boucle d'un run (pseudo-code)
```python
async def run_loop(run, bot: BotConnection, engine: Engine):
    state = load_level(run.level, seed=run.seed)
    while not state.finished:
        await bot.send(observe(state))
        try:
            action = await asyncio.wait_for(bot.recv_action(), timeout=cfg.tick_timeout)
        except asyncio.TimeoutError:
            action = Action.WAIT
        state, events = engine.step(state, action)
        await event_bus.publish(run, events, state)   # succès, score, replay, diffusion
        await asyncio.sleep(0)                        # laisse respirer les autres runs
```

---

## 7. Diffusion en direct

- `WS /ws/live` : flux du **run vedette** (pour l'écran projeté).
- `WS /ws/live/{run_id}` : flux d'un run précis (pour un mode mosaïque 5 écrans).
- `GET /api/runs/active` : liste des runs en cours avec progression.

**Sélection du run vedette** (`featured.py`), recalculée chaque seconde :
1. niveau le plus avancé ;
2. à égalité : progression dans le niveau (distance restante à la sortie / PV du boss) ;
3. **hystérésis** : on ne change de vedette que si l'écart persiste ≥ 5 s (évite le clignotement).
4. Bonus « moments forts » : un événement `BossPhaseChanged`, `LevelCompleted` ou `AchievementUnlocked` force la vedette pendant 5 s.

**Débit** : la simulation peut aller plus vite que l'affichage. Le hub envoie des **snapshots throttlés** (ex. 10 fps max) + les événements importants ; le front interpole. Le replay complet reste disponible après coup (`GET /api/runs/{id}/replay`).

---

## 8. Succès

### 8.1 Mécanique
```python
class Achievement:
    id: str; name: str; hidden: bool; hint: str; points: int
    scope: Literal["run", "team"]           # évalué dans un run ou cumulé sur l'événement
    def on_event(self, ctx: AchievementContext, event: Event) -> bool: ...
```
Le `AchievementService` écoute l'EventBus, stocke la progression par équipe (`TeamAchievementProgress`, JSON libre) et émet `AchievementUnlocked` (diffusé en direct, gros effet à l'écran). Les succès cachés s'affichent « ??? » avec leur **indice**, éventuellement révélé progressivement (indice 1 au début, indice 2 après 1 h via l'admin).

### 8.2 Proposition de 15 succès (réalisables en 2 h)

| # | Nom | Condition | Indice donné |
|---|---|---|---|
| 1 | **Je suis en retard !** | Campagne complète en < 15 min (temps in-game : 1 tick = 1 s → 900 ticks) | « Le Lapin n'a jamais le temps… » |
| 2 | **Qu'on leur coupe la tête** | Tuer tous les mobs de tous les niveaux (cumul équipe) | « Ne laissez personne derrière vous. » |
| 3 | **Collectionneur de chapeaux** | Ramasser les 5+ chapeaux du Chapelier | « Le Chapelier a perdu quelque chose à chaque étape. » |
| 4 | **Plus mort que vif** | Mourir au moins une fois dans chaque niveau | « L'échec est aussi un chemin. » |
| 5 | **Partie de croquet truquée** | Vaincre la Reine sans lui infliger de dégât direct | « La Reine ne regarde jamais où elle met les pieds. » |
| 6 | **Bois-moi** | Rétrécir et passer la petite porte du niveau 1 | « Certaines portes ne sont pas faites pour votre taille. » |
| 7 | **Il est toujours six heures** | Rester 6 ticks immobile sur la chaise vide de la table du thé | « Au thé, il faut savoir s'asseoir. » |
| 8 | **Le sourire sans le chat** | Trouver la case du Chat du Cheshire (invisible, niveau 3) | « Certains n'apparaissent qu'à ceux qui attendent. » |
| 9 | **Conseil de la Chenille** | Attendre à côté de la Chenille et recevoir son indice | « Qui êtes-vous ? » |
| 10 | **Garde royale** | 10 parades parfaites dans un même run | « La meilleure attaque… » |
| 11 | **Sans une égratignure** | Finir le niveau 2 sans perdre de PV | « Un thé, pas une bagarre. » |
| 12 | **Le chemin le plus court** | Finir le niveau 4 sans jamais repasser par une case | « Tout droit, sans hésiter. » |
| 13 | **Peindre les roses en rouge** | « Peindre » (attaquer) toutes les roses blanches du niveau 4 | « La Reine déteste le blanc. » |
| 14 | **Le couteau suffit** | Vaincre la Reine uniquement au couteau | « Un vrai duel ne se fait pas de loin. » |
| 15 | **Code propre** | Un run complet sans aucune action invalide ni timeout | « Le Lapin déteste attendre une réponse. » |
| bonus | **Premier arrivé** | Première équipe à finir un niveau donné (1 seule équipe par niveau) | — |

Tous reposent sur des événements déjà nécessaires au moteur (`Moved`, `Waited`, `PerfectParry`, `MobKilled`, `ItemPicked`, `PlayerDied`, `DamageDealt(source=…)`, `LevelCompleted`, `InvalidAction`, `Timeout`).

---

## 9. Score et classement

**Score d'un run campagne** (proposition, à équilibrer après playtest) :
```
score = Σ niveaux complétés × 1000
      + bonus_temps   (max(0, par_ticks - ticks_utilisés) × 2 par niveau)
      + kills × 20 + chapeaux × 50
      − morts × 100
```
**Classement d'équipe** :
1. **Niveau max atteint** (critère principal — c'est la progression qui compte) ;
2. **meilleur score de campagne** ;
3. **points de succès** (chaque succès vaut 50–200 pts selon difficulté) ;
4. départage : timestamp d'atteinte.

Endpoint : `GET /api/leaderboard` (+ push WS `LeaderboardUpdated` pour l'écran public). Option : **gel du classement** les 15 dernières minutes pour le suspense, révélé à la fin.

---

## 10. API (résumé)

| Méthode | Route | Rôle |
|---|---|---|
| WS | `/ws/bot?token=…&mode=practice&level=3` | Connexion du bot, lance un run |
| WS | `/ws/live`, `/ws/live/{run_id}` | Spectateurs |
| GET | `/api/levels` | Niveaux + débloqués pour l'équipe |
| GET | `/api/runs/active`, `/api/runs/{id}`, `/api/runs/{id}/replay` | Runs |
| GET | `/api/leaderboard` | Classement |
| GET | `/api/teams/me/achievements` | Succès (cachés = indice) |
| POST | `/api/admin/…` | reset, stop run, freeze, révéler indices, créer équipes |

Le protocole bot est décrit en **Pydantic** → export **JSON Schema** → génération des types TS pour le projet Angular. Un seul contrat, deux SDK.

**Messages bot** :
```
server → bot : {"type": "hello", "run_id", "level", "rules": {...}}
server → bot : {"type": "observation", ...}          # chaque tick
bot → server : {"type": "action", "tick": 42, "action": "MOVE_UP"}
server → bot : {"type": "level_complete" | "died" | "run_end", "summary": {...}}
```
Le champ `tick` dans la réponse évite qu'une réponse en retard soit appliquée au mauvais tick.

---

## 11. Propositions pour compléter le jeu

1. **Bot de référence interne** par niveau (dans `tests/levels/`) : prouve que chaque niveau est faisable et donne les `par_ticks` du score.
2. **Mode « debug » pour les joueurs** : `/ws/bot?...&debug=1` renvoie la grille complète après la fin d'un niveau (pas pendant) pour comprendre leurs erreurs.
3. **Seeds** : seed fixe en practice (reproductible pour débugger), seed aléatoire en campagne (anti hard-code de la séquence d'actions !). Les variantes de niveau 3/4 (placement des pièges) doivent changer avec le seed, sinon une équipe peut juste enregistrer une suite de moves.
4. **Replays** téléchargeables par l'équipe : énorme gain pédagogique.
5. **Indices payants** (option) : une équipe peut « acheter » un indice de succès contre des points.
6. **Mini-jauge « Folie »** : chaque action invalide augmente la folie ; à 100 l'écran du joueur se renverse (effet visuel côté front) — fun et pousse à coder proprement.
7. **SDK minimal mais pas trop** : fournir la boucle réseau + modèles, laisser vide `def decide(obs) -> Action`. Fournir un exemple de bot « random walk » qui finit (lentement) le niveau 1.
8. **Écran public** : mosaïque des 5 runs en petit + run vedette en grand + fil d'événements (« L'équipe X vient de débloquer ??? »).
9. Cohérence du lore : tu parles de *Reine Rouge* et de *Reine de Cœur* ; dans le conte original ce sont deux personnages différents (la Reine Rouge vient de *De l'autre côté du miroir*). À trancher pour les textes.

---

## 12. Plan de réalisation jusqu'à décembre

| Étape | Contenu | Livrable testable |
|---|---|---|
| 1 | `engine/` : grid, entités, déplacements, `step()`, observation, loader ASCII | Tests pytest, niveau 1 jouable en local par un bot Python appelé en direct |
| 2 | Combat (attaque, parade, télégraphe), 2 IA de mobs, niveau 2 | Bot de référence niveau 2 |
| 3 | `runs/` + `bot_gateway` WebSocket + SDK Python minimal | Un bot distant finit le niveau 1 |
| 4 | Brouillard, pièges, niveaux 3 et 4, loader Tiled | Bots de référence 3–4 |
| 5 | Boss + niveau 5 | Bot de référence 5 |
| 6 | EventBus, succès, score, persistance SQLite, leaderboard | Tableau des succès |
| 7 | Broadcast + run vedette + replays | Écran spectateur minimal |
| 8 | SDK TS / Angular, admin, playtest avec 5 bots en parallèle (test de charge) | Répétition générale |

## 13. Décisions prises

| Sujet | Décision |
|---|---|
| Chrono « 15 min » | **Temps in-game** : 1 tick = 1 s, campagne complète en < 900 ticks. |
| Mort | **Fin du run** (practice : on relance le niveau ; campagne : retour au niveau 1). |
| Runs simultanés | **1 practice + 1 campagne** par équipe, 10 runs max au total. |
| Brouillard | **Niveau 3 uniquement** ; niveaux 4–5 en vision totale. |

⚠️ Point d'attention : avec « mort = fin du run » et une campagne < 900 ticks, le succès *Je suis en retard !* est exigeant. Calibrer les `par_ticks` des 5 niveaux pour que la somme du bot de référence soit ≈ 600 ticks (marge de 50 %).
