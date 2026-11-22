"""Équipes et authentification par token.

Le fichier teams.json (à la racine, NON versionné) ressemble à teams.example.json :
    [{"id": "team1", "name": "Les Chapeliers", "token": "..."}]
Générer des tokens : python -c "import secrets; print(secrets.token_urlsafe(16))"
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Team:
    id: str
    name: str
    token: str


class TeamRegistry:
    def __init__(self, teams: list[Team]) -> None:
        ids = [t.id for t in teams]
        if len(ids) != len(set(ids)):
            raise ValueError("Identifiants d'équipe en double")
        self._by_id = {t.id: t for t in teams}

    @classmethod
    def from_file(cls, path: Path) -> TeamRegistry:
        if not path.exists():
            raise FileNotFoundError(
                f"{path} introuvable : copie teams.example.json en teams.json et change les tokens"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls([Team(**entry) for entry in data])

    def authenticate(self, token: str | None) -> Team | None:
        if not token:
            return None
        for team in self._by_id.values():
            # compare_digest : comparaison en temps constant (évite de deviner un token octet par octet)
            if secrets.compare_digest(team.token, token):
                return team
        return None

    def get(self, team_id: str) -> Team | None:
        return self._by_id.get(team_id)

    def all(self) -> list[Team]:
        return list(self._by_id.values())
