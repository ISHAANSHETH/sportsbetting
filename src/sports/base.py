"""Abstract base class for sport-specific prediction handlers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PredictionResult:
    sport: str
    entity1: str                    # home team / player 1
    entity2: str                    # away team / player 2
    date: str
    probabilities: dict             # {outcome: float}
    market_probs: Optional[dict]    # from Polymarket/Kalshi
    edges: dict                     # {outcome: {edge, rating, ...}}
    best_bet: Optional[str]
    best_edge_pct: float
    kelly_stake_pct: float
    confidence: float               # 0-100
    key_factors: list               # list of strings
    news_flags: list                # negative news items
    data_sources: list              # which scrapers were used
    model_breakdown: dict           # individual model contributions
    venue: str = "Unknown"
    competition: str = ""
    is_neutral: bool = False


class AbstractSport(ABC):
    """Base class for all sport handlers."""

    @property
    @abstractmethod
    def sport_name(self) -> str:
        pass

    @property
    @abstractmethod
    def sport_keywords(self) -> list:
        """Keywords that identify this sport in natural language."""
        pass

    @abstractmethod
    def predict(
        self,
        entity1: str,
        entity2: str,
        date: str,
        context: dict,
    ) -> PredictionResult:
        """Run the full prediction pipeline."""
        pass

    def matches_sport(self, text: str) -> bool:
        """Check if input text seems to be about this sport."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.sport_keywords)
