"""Protocole WebSocket entre le serveur et les bots (JSON).

Serveur → bot :
    hello        : début de partie (run_id, mode, niveaux, délai par tick)
    level_start  : début d'un niveau
    observation  : à chaque tick ; le bot DOIT répondre par une action
    level_end    : fin d'un niveau (WON / DEAD / TIMEOUT)
    run_end      : fin de la partie
    error        : refus de connexion ou message invalide

Bot → serveur :
    {"type": "action", "tick": 42, "action": "MOVE_UP"}
    Le champ `tick` doit reprendre celui de l'observation : une réponse en retard
    (tick précédent) est ignorée au lieu d'être appliquée au mauvais moment.

Ces modèles Pydantic servent aussi à générer le JSON Schema pour le SDK Angular.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ValidationError

PROTOCOL_VERSION = 1


class Hello(BaseModel):
    type: Literal["hello"] = "hello"
    protocol_version: int = PROTOCOL_VERSION
    run_id: str
    team: str
    mode: str
    levels: list[int]
    tick_timeout: float


class LevelStart(BaseModel):
    type: Literal["level_start"] = "level_start"
    level: int
    name: str
    seed: int | None = None  # communiqué seulement en entraînement


class ObservationMessage(BaseModel):
    type: Literal["observation"] = "observation"
    run_id: str
    level: int
    tick: int
    data: dict[str, Any]


class LevelEnd(BaseModel):
    type: Literal["level_end"] = "level_end"
    level: int
    status: str
    ticks: int
    hp: int


class RunEnd(BaseModel):
    type: Literal["run_end"] = "run_end"
    status: str
    levels_completed: list[int]
    total_ticks: int
    score: int = 0
    achievements: list[str] = []  # noms des succès débloqués pendant cette partie
    reason: str = ""


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    message: str


class ActionMessage(BaseModel):
    type: Literal["action"] = "action"
    tick: int
    action: str


def parse_action(raw: Any) -> ActionMessage | None:
    """Valide un message reçu du bot ; None s'il est mal formé."""
    try:
        return ActionMessage.model_validate(raw)
    except ValidationError:
        return None


def json_schemas() -> dict[str, Any]:
    """JSON Schema de tous les messages (pour générer les types TypeScript)."""
    models = [Hello, LevelStart, ObservationMessage, LevelEnd, RunEnd, ErrorMessage, ActionMessage]
    return {model.__name__: model.model_json_schema() for model in models}
