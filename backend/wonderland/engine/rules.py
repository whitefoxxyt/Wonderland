"""Constantes d'équilibrage.

Tout ce qu'on voudra ajuster après un playtest est regroupé ici :
on ne doit jamais trouver de « nombre magique » ailleurs dans le moteur.
"""

# ---------- joueur ----------
PLAYER_MAX_HP = 5
KNIFE_DAMAGE = 1
POTION_HEAL = 2

# Lance-sucres du Chapelier (arme à distance)
LAUNCHER_DAMAGE = 1
LAUNCHER_RANGE = 6
LAUNCHER_SPEED = 2  # cases parcourues par tick
LAUNCHER_COOLDOWN = 3  # ticks entre deux tirs

# ---------- combat ----------
MOB_STRIKE_COOLDOWN = 1  # ticks après une frappe avant de pouvoir ré-armer
PARRY_STUN_TICKS = 2  # étourdissement d'un mob après une parade réussie

# ---------- pièges ----------
TRAP_REVEAL_RADIUS = 1  # un piège caché se révèle quand le joueur passe à côté
BOSS_TRAP_MULTIPLIER = 2  # « la Reine ne regarde jamais où elle met les pieds »

# ---------- charge de la Reine ----------
CHARGE_SPEED = 2  # cases par tick
CHARGE_MAX_TURNS = 6
CHARGE_DAMAGE = 2
CHARGE_STUN_TICKS = 3  # si elle percute un mur / un pilier / un piège actif

# ---------- catalogue des mobs ----------
# kind -> caractéristiques. `brain` est le nom de l'IA (voir engine/ai).
# `move_every` = 2 signifie que le mob n'agit qu'un tick sur deux.
MOB_TYPES: dict[str, dict] = {
    "dormouse": {"hp": 1, "damage": 1, "brain": "chaser", "sight": 4, "move_every": 2},
    "march_hare": {"hp": 2, "damage": 1, "brain": "erratic", "sight": 6, "move_every": 1},
    "card_guard": {"hp": 2, "damage": 1, "brain": "patrol", "sight": 5, "move_every": 1},
    "card_archer": {"hp": 1, "damage": 1, "brain": "archer", "sight": 7, "move_every": 1},
    "queen": {
        "hp": 20,
        "damage": 2,
        "brain": "queen",
        "sight": 40,
        "move_every": 2,
        "is_boss": True,
    },
}
