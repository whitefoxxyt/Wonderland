# Wonderland — fiche d'exploitation (jour J)

## 1. Préparation (la veille)
1. Installer le serveur (venv activé, à la racine du projet) :
   ```bash
   python -m pip install -e ".[server]"
   ```
2. Créer `teams.json` à partir de `teams.example.json`, avec un token par équipe :
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(16))"
   ```
3. Choisir un token admin (garder-le pour soi).
4. Distribuer aux équipes : `sdk/python/` ou `sdk/typescript/`, leur token et l'adresse du serveur.
5. Vérifier que tout est vert : `python -m pytest`.

## 2. Lancer le serveur
PowerShell :
```powershell
$env:WONDERLAND_ADMIN_TOKEN = "votre-token-admin"
uvicorn wonderland.api.app:create_app --factory --host 0.0.0.0 --port 8000
```
- Écran public : `http://IP_DU_SERVEUR:8000/live` (vedette) ou `/live?mode=all` (mosaïque).
- Documentation de l'API : `http://IP_DU_SERVEUR:8000/docs`.
- Penser à autoriser le port 8000 dans le pare-feu Windows.

### Réglages (variables d'environnement `WONDERLAND_…`)
| Variable | Défaut | Rôle |
|---|---|---|
| `TICK_TIMEOUT` | 0.3 | secondes max pour répondre à un tick |
| `CAMPAIGN_TICK_DELAY` | 0.1 | durée mini d'un tick en campagne (lisibilité du direct) |
| `RUN_COOLDOWN` | 3 | secondes entre deux lancements d'une équipe |
| `MAX_CONCURRENT_RUNS` | 10 | parties simultanées max |
| `LIVE_FPS` | 10 | images/s envoyées aux spectateurs par partie |
| `UNLOCK_ALL` | 0 | 1 = tous les niveaux ouverts en entraînement |
| `DB_PATH` | wonderland.db | base SQLite |
| `TEAMS_FILE` | teams.json | fichier des équipes |
| `ADMIN_TOKEN` | (vide) | active les routes admin |

## 3. Répétition générale
Serveur lancé, puis dans un autre terminal :
```bash
python tools/rehearsal.py --url ws://localhost:8000 --teams teams.json
```
10 parties simultanées (une campagne + un entraînement « difficile » par équipe) et 3 écrans spectateurs.
**Ensuite, remettre à zéro** (voir ci-dessous).

## 4. Commandes admin pendant l'événement
Toutes avec l'en-tête `X-Admin-Token`. Exemple PowerShell :
```powershell
$h = @{ "X-Admin-Token" = "votre-token-admin" }
Invoke-RestMethod http://localhost:8000/api/admin/status -Headers $h
Invoke-RestMethod http://localhost:8000/api/admin/hints -Method Post -Headers $h -ContentType "application/json" -Body '{"level": 2}'
```
| Quand | Route | Corps |
|---|---|---|
| Voir les parties et latences | `GET /api/admin/status` | |
| Après ~1 h : 2ᵉ indice des succès | `POST /api/admin/hints` | `{"level": 2}` |
| Message sur les écrans | `POST /api/admin/announce` | `{"text": "Plus que 15 minutes !"}` |
| 15 min avant la fin : suspense | `POST /api/admin/leaderboard/freeze` | `{"value": true}` |
| Vrai classement (pour l'orga) | `GET /api/admin/leaderboard` | |
| Fin du temps : plus de parties | `POST /api/admin/accept-runs` | `{"value": false}` |
| Arrêter une partie | `POST /api/admin/runs/{id}/stop` | |
| Arrêter toutes les parties | `POST /api/admin/runs/stop-all` | |
| Annonce des résultats | `POST /api/admin/leaderboard/freeze` | `{"value": false}` |
| Remise à zéro (après la répétition) | `POST /api/admin/reset` | `{"confirm": "RESET"}` |

## 5. En cas de problème
- **Une équipe soupçonnée de jouer à la main** : `GET /api/admin/status` → `latency` de sa partie.
  Un bot répond en quelques ms ; un humain en centaines de ms, avec beaucoup de `timeouts`.
- **Le serveur redémarre** : parties en cours perdues, mais niveaux débloqués, succès
  et classement sont conservés (base SQLite).
- **Rejouer une partie** : `GET /api/runs/{id}/replay/{n}` (toutes les images du niveau n).
