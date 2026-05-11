"""Kelly Criterion stake sizing — quarter-Kelly for safety."""


def kelly_fraction(
    prob: float,
    decimal_odds: float,
    fraction: float = 0.25,
) -> float:
    """
    Quarter-Kelly criterion.
    prob: model win probability
    decimal_odds: e.g. 2.10 for +110 / evens+
    fraction: Kelly fraction (0.25 = quarter-Kelly, safest)
    Returns: % of bankroll to stake (0.0–100.0)
    """
    b = decimal_odds - 1.0  # net profit per unit staked
    q = 1.0 - prob
    f_full = (b * prob - q) / b
    f = f_full * fraction
    return round(max(0.0, f * 100), 2)


def kelly_from_american(prob: float, american_odds: float, fraction: float = 0.25) -> float:
    """Kelly from American odds."""
    if american_odds >= 0:
        decimal = american_odds / 100.0 + 1.0
    else:
        decimal = 100.0 / abs(american_odds) + 1.0
    return kelly_fraction(prob, decimal, fraction)


def expected_value(prob: float, decimal_odds: float) -> float:
    """
    Expected value per unit staked.
    EV > 0 → positive expectation bet.
    """
    return round(prob * (decimal_odds - 1) - (1 - prob), 4)


def stake_recommendation(kelly_pct: float, bankroll: float = 1000.0) -> str:
    """Human-readable stake recommendation."""
    stake = bankroll * kelly_pct / 100
    if kelly_pct == 0:
        return "No bet (negative edge)"
    return f"${stake:.2f} (Kelly: {kelly_pct:.1f}% of bankroll)"
