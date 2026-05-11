"""Odds format conversions and vig removal."""


def american_to_prob(odds: float) -> float:
    """Convert American odds to implied probability (with vig)."""
    if odds >= 100:
        return 100.0 / (odds + 100.0)
    else:
        return abs(odds) / (abs(odds) + 100.0)


def prob_to_american(prob: float) -> int:
    """Convert probability to American moneyline."""
    if prob >= 0.5:
        return int(-(prob / (1 - prob)) * 100)
    else:
        return int((1 - prob) / prob * 100)


def decimal_to_prob(odds: float) -> float:
    """Convert decimal odds (e.g. 2.10) to implied probability."""
    return 1.0 / odds


def prob_to_decimal(prob: float) -> float:
    """Convert probability to decimal odds."""
    return round(1.0 / prob, 3) if prob > 0 else 999.0


def remove_vig(raw_probs: dict) -> dict:
    """
    Remove bookmaker's vig (overround) by normalizing probabilities to sum to 1.
    raw_probs: dict of outcome → implied probability (may sum to > 1.0 due to vig)
    """
    total = sum(v for v in raw_probs.values() if v is not None)
    if total <= 0:
        return raw_probs
    return {k: round(v / total, 4) if v is not None else None for k, v in raw_probs.items()}


def format_odds_display(prob: float, show_american: bool = True) -> str:
    """Format probability + American odds for display."""
    american = prob_to_american(prob)
    sign = "+" if american > 0 else ""
    return f"{prob * 100:.1f}% ({sign}{american})"
