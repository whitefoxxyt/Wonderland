"""Choix de la partie « vedette » affichée en grand sur l'écran public.

Règles :
    1. la partie la plus avancée gagne (niveau, puis progression dans le niveau) ;
    2. hystérésis : on ne change de vedette que si un challenger reste devant
       pendant `hold` secondes (évite que l'écran saute sans arrêt) ;
    3. moment fort (niveau gagné, mort, phase du boss, succès) : la partie
       concernée prend la vedette pendant `highlight` secondes.
"""

from __future__ import annotations

Score = tuple[float, ...]


class FeaturedSelector:
    def __init__(self, hold: float = 5.0, highlight: float = 5.0) -> None:
        self.hold = hold
        self.highlight_duration = highlight
        self.current: str | None = None
        self._challenger: str | None = None
        self._challenger_since = 0.0
        self._highlight: tuple[str, float] | None = None  # (run_id, fin)

    def highlight(self, run_id: str, now: float) -> None:
        self._highlight = (run_id, now + self.highlight_duration)

    def update(self, scores: dict[str, Score], now: float) -> str | None:
        """Renvoie la partie vedette à l'instant `now` parmi `scores` (run_id → score)."""
        if self._highlight is not None:
            run_id, until = self._highlight
            if now < until and run_id in scores:
                self.current = run_id
                return run_id
            # Fin du moment fort : on revient tout de suite à la partie la plus avancée.
            self._highlight = None
            self.current = None

        if not scores:
            self.current = None
            return None
        best = max(scores, key=lambda run_id: (scores[run_id], run_id))
        if self.current not in scores:
            self.current = best
            self._challenger = None
            return best
        if best == self.current or scores[best] <= scores[self.current]:
            self._challenger = None
            return self.current

        if best != self._challenger:
            self._challenger, self._challenger_since = best, now
        elif now - self._challenger_since >= self.hold:
            self.current, self._challenger = best, None
        return self.current
