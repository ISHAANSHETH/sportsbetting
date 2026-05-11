"""Probability calibration and ensemble blending utilities."""
import numpy as np
from typing import Optional


def normalize(probs: dict) -> dict:
    """Ensure probabilities sum to 1.0."""
    total = sum(v for v in probs.values() if v is not None)
    if total <= 0:
        n = sum(1 for v in probs.values() if v is not None)
        return {k: (1.0 / n if v is not None else None) for k, v in probs.items()}
    return {k: (round(v / total, 4) if v is not None else None) for k, v in probs.items()}


def blend(
    probs_list: list,
    weights: list,
    keys: list,
) -> dict:
    """
    Weighted soft ensemble of multiple probability dicts.
    probs_list: list of {key: float} dicts
    weights: list of floats (will be normalized to sum to 1)
    keys: outcome keys to blend
    """
    w_total = sum(weights)
    w_norm = [w / w_total for w in weights]

    result = {}
    for k in keys:
        total = 0.0
        w_used = 0.0
        for probs, w in zip(probs_list, w_norm):
            val = probs.get(k)
            if val is not None:
                total += val * w
                w_used += w
        result[k] = round(total / w_used, 4) if w_used > 0 else None

    return normalize(result)


def apply_news_sentiment(probs: dict, sentiment: dict, team_key: str) -> dict:
    """
    Adjust probabilities based on news sentiment score for a team.
    sentiment: {score: float (-0.5 to 0.3), flags: list}
    team_key: 'home_win' or 'away_win'
    """
    score = sentiment.get("score", 0.0)
    if abs(score) < 0.05:
        return probs  # no meaningful adjustment

    # Scale: sentiment of -0.5 → max 8% probability reduction
    adjustment = score * 0.16  # -0.5 * 0.16 = -0.08 max

    result = dict(probs)
    if team_key in result and result[team_key] is not None:
        result[team_key] = max(0.01, result[team_key] + adjustment)

    return normalize(result)


def apply_injury_adjustment(
    probs: dict,
    home_availability: float,
    away_availability: float,
    home_key: str = "home_win",
    away_key: str = "away_win",
) -> dict:
    """
    Adjust based on squad availability (0.0–1.0).
    Full squad = 1.0; star player injured = ~0.85.
    """
    home_adj = (home_availability - 1.0) * 0.15  # max ±15%
    away_adj = (away_availability - 1.0) * 0.15

    result = dict(probs)
    if home_key in result and result[home_key] is not None:
        result[home_key] = max(0.01, result[home_key] + home_adj)
    if away_key in result and result[away_key] is not None:
        result[away_key] = max(0.01, result[away_key] + away_adj)

    return normalize(result)


def confidence_score(probs: dict, keys: list = None) -> float:
    """
    Model confidence: 0–100.
    Higher = model strongly favors one outcome.
    50 = equivalent to a coin flip (uniform distribution).
    """
    vals = [v for v in probs.values() if v is not None]
    if not vals:
        return 50.0

    max_p = max(vals)
    uniform = 1.0 / len(vals)
    # Normalize: 0 at uniform, 100 at certainty
    score = (max_p - uniform) / (1.0 - uniform) * 100
    return round(max(0, min(100, score)), 1)
