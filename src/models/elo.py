"""Universal ELO rating system — supports surface-specific ratings for tennis."""
import math
from typing import Optional


def win_probability(elo_a: float, elo_b: float) -> float:
    """P(A beats B) using standard Elo formula."""
    return 1.0 / (1.0 + math.pow(10, (elo_b - elo_a) / 400.0))


def update_elo(elo_a: float, elo_b: float, result: float, k: float = 32.0) -> tuple:
    """
    Update Elo ratings after a match.
    result: 1.0 = A won, 0.5 = draw, 0.0 = B won.
    Returns (new_elo_a, new_elo_b).
    """
    exp_a = win_probability(elo_a, elo_b)
    exp_b = 1.0 - exp_a
    new_a = elo_a + k * (result - exp_a)
    new_b = elo_b + k * ((1 - result) - exp_b)
    return round(new_a, 2), round(new_b, 2)


def k_factor(matches_played: int, top_level: bool = True) -> float:
    """Dynamic K-factor: higher for newer players, lower for established."""
    if matches_played < 30:
        return 40.0
    if top_level:
        return 20.0
    return 32.0


def surface_elo(
    base_elo: float,
    surface: str,
    surface_win_rate: float,
    overall_win_rate: float,
) -> float:
    """
    Adjust Elo for a specific surface based on relative performance.
    surface_win_rate / overall_win_rate ratio shifts base Elo up or down.
    """
    if overall_win_rate <= 0:
        return base_elo
    ratio = surface_win_rate / overall_win_rate
    adjustment = (ratio - 1.0) * 150  # ±150 pts max
    return round(base_elo + adjustment, 1)


class EloPredictor:
    """
    Manages Elo ratings for a set of players/teams.
    Supports per-surface ratings for tennis.
    """

    TENNIS_SURFACES = ["hard", "clay", "grass", "carpet"]

    def __init__(self, default_elo: float = 1500.0):
        self.default_elo = default_elo
        self.ratings: dict = {}
        self.surface_ratings: dict = {}  # {player: {surface: elo}}

    def get(self, entity: str, surface: Optional[str] = None) -> float:
        if surface and surface in self.TENNIS_SURFACES:
            surf_map = self.surface_ratings.get(entity, {})
            return surf_map.get(surface, self.ratings.get(entity, self.default_elo))
        return self.ratings.get(entity, self.default_elo)

    def set(self, entity: str, elo: float, surface: Optional[str] = None):
        if surface:
            if entity not in self.surface_ratings:
                self.surface_ratings[entity] = {}
            self.surface_ratings[entity][surface] = elo
        else:
            self.ratings[entity] = elo

    def predict(
        self,
        entity_a: str,
        entity_b: str,
        surface: Optional[str] = None,
        home_advantage: float = 0.0,
    ) -> dict:
        """
        Predict win probabilities.
        home_advantage: additional Elo points for home team (football: ~65 pts).
        Returns {a_win: float, draw: float, b_win: float}.
        """
        elo_a = self.get(entity_a, surface) + home_advantage
        elo_b = self.get(entity_b, surface)

        p_a = win_probability(elo_a, elo_b)
        p_b = 1.0 - p_a

        # For football/cricket: estimate draw probability using Bradley-Terry extension
        draw_prob = _estimate_draw_prob(elo_a - home_advantage, elo_b)

        # Rescale
        p_a_adj = p_a * (1 - draw_prob)
        p_b_adj = p_b * (1 - draw_prob)

        return {
            "a_win": round(p_a_adj, 4),
            "draw": round(draw_prob, 4),
            "b_win": round(p_b_adj, 4),
        }

    def predict_1v1(self, entity_a: str, entity_b: str, surface: Optional[str] = None) -> float:
        """P(A wins) for 1v1 sports (tennis, UFC, boxing). No draw."""
        elo_a = self.get(entity_a, surface)
        elo_b = self.get(entity_b, surface)
        return round(win_probability(elo_a, elo_b), 4)

    def seed_from_dict(self, ratings: dict, surface: Optional[str] = None):
        """Load seeded Elo ratings from a dictionary."""
        for entity, elo in ratings.items():
            self.set(entity, float(elo), surface)


def _estimate_draw_prob(elo_a: float, elo_b: float) -> float:
    """
    Estimate draw probability for football based on Elo closeness.
    Closer Elo → higher draw probability. Peak around ~28% for equal teams.
    Based on Dixon-Coles empirical observation.
    """
    elo_diff = abs(elo_a - elo_b)
    # Logistic decay: max draw ~0.28 at diff=0, min ~0.08 at diff=400
    draw = 0.28 * math.exp(-elo_diff / 600)
    return round(max(0.08, min(0.32, draw)), 4)


# Default global predictor instance
_global = EloPredictor(default_elo=1500.0)


def get_global() -> EloPredictor:
    return _global
