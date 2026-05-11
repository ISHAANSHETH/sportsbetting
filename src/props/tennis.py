"""Tennis prop calculators: first set, tiebreak, number of sets O/U."""
import math


# ── Serve-based model ─────────────────────────────────────────────────────────
# Each player has a serve_hold_prob (probability of holding serve).
# From this we can derive P(game won | serving), then P(set won).

SURFACE_SERVE_HOLD = {
    "grass":  0.72,   # grass inflates serve holds
    "hard":   0.65,
    "clay":   0.60,   # clay deflates serve, longer rallies
    "carpet": 0.67,
}

# Seeded surface-adjusted serve hold probabilities for top players
PLAYER_SERVE_SEEDS = {
    "novak djokovic":    {"grass": 0.78, "hard": 0.76, "clay": 0.72},
    "carlos alcaraz":    {"grass": 0.75, "hard": 0.74, "clay": 0.73},
    "jannik sinner":     {"grass": 0.74, "hard": 0.75, "clay": 0.71},
    "rafael nadal":      {"grass": 0.72, "hard": 0.73, "clay": 0.78},
    "daniil medvedev":   {"grass": 0.72, "hard": 0.74, "clay": 0.68},
    "stefanos tsitsipas":{"grass": 0.71, "hard": 0.72, "clay": 0.73},
    "alexander zverev":  {"grass": 0.73, "hard": 0.72, "clay": 0.72},
    "andrey rublev":     {"grass": 0.70, "hard": 0.71, "clay": 0.70},
    "iga swiatek":       {"grass": 0.70, "hard": 0.72, "clay": 0.78},
    "aryna sabalenka":   {"grass": 0.72, "hard": 0.74, "clay": 0.70},
    "coco gauff":        {"grass": 0.69, "hard": 0.70, "clay": 0.71},
    "elena rybakina":    {"grass": 0.74, "hard": 0.71, "clay": 0.69},
    "jessica pegula":    {"grass": 0.68, "hard": 0.70, "clay": 0.68},
}


def _serve_hold(player: str, surface: str) -> float:
    """Return serve hold probability for a player on a surface."""
    key = player.lower()
    for seed_name, surfaces in PLAYER_SERVE_SEEDS.items():
        if seed_name in key or key in seed_name:
            return surfaces.get(surface, surfaces.get("hard", 0.68))
    return SURFACE_SERVE_HOLD.get(surface, 0.65)


def _p_set(server_hold: float, returner_hold: float) -> float:
    """
    P(server wins a set) using a geometric set model.
    Approximates P(win set from 0-0) using serve game probabilities.
    """
    # Probability of winning a game on serve
    ps = server_hold
    pr = returner_hold  # returner winning their serve game

    # Simple approximation: P(player wins set) via Markov-like formula
    # Based on: each player alternates serving, 6 games to win set (with tiebreak)
    # Simplified formula commonly used in tennis modelling
    ratio = ps / (ps + (1 - pr)) if (ps + (1 - pr)) > 0 else 0.5
    return max(0.05, min(0.95, ratio))


def _p_tiebreak_in_set(server_hold: float, returner_hold: float) -> float:
    """P(set reaches tiebreak) = P(6-6)."""
    # Each game: p_server wins it (server_hold), p_returner wins (1-server_hold)
    # In a set: games alternate server. Rough formula for P(6-6).
    # P(reach 6-6) ≈ P(both reach 6 games) from a simplified model
    p_game_server = server_hold
    p_game_returner = returner_hold
    # P(neither breaks early) — approximate
    p_tb = (p_game_server * p_game_returner) ** 3  # very rough but directionally correct
    return max(0.05, min(0.55, p_tb * 4))  # scale to reasonable range


# ── First Set Winner ──────────────────────────────────────────────────────────

def first_set_winner(p1: str, p2: str, surface: str = "hard",
                     p1_win_match = 0.55) -> dict:
    p1_win_match = float(p1_win_match)
    """P(p1 wins first set) and P(p2 wins first set)."""
    p1_hold = _serve_hold(p1, surface)
    p2_hold = _serve_hold(p2, surface)

    # P(p1 wins set when serving first) — approximate
    p1_set_as_server = _p_set(p1_hold, p2_hold)
    p2_set_as_server = _p_set(p2_hold, p1_hold)

    # Average over who serves first (unknown, so 50/50)
    p1_set = 0.5 * p1_set_as_server + 0.5 * (1 - p2_set_as_server)

    # Blend with match win prob (match-level form should inform set)
    p1_set = 0.75 * p1_set + 0.25 * p1_win_match
    p1_set = max(0.05, min(0.95, p1_set))

    factors = [
        f"{p1} serve hold ({surface}): {p1_hold:.0%}",
        f"{p2} serve hold ({surface}): {p2_hold:.0%}",
        f"Match form blended: {float(p1_win_match):.0%} → {float(p1_set):.0%} set win",
    ]

    return {
        "probs": {"p1_set1": round(p1_set, 4), "p2_set1": round(1 - p1_set, 4)},
        "factors": factors,
        "breakdown": {"Serve model": {"p1_set1": round(p1_set, 4), "p2_set1": round(1 - p1_set, 4)}},
        "prop_description": f"{p1} wins First Set",
    }


# ── Tiebreak in Match ─────────────────────────────────────────────────────────

def tiebreak_in_match(p1: str, p2: str, surface: str = "hard",
                      best_of: int = 3, p1_win_match: float = 0.55) -> dict:
    """P(at least one tiebreak occurs in the match)."""
    p1_hold = _serve_hold(p1, surface)
    p2_hold = _serve_hold(p2, surface)

    p_tb_per_set = max(
        _p_tiebreak_in_set(p1_hold, p2_hold),
        _p_tiebreak_in_set(p2_hold, p1_hold),
    )

    # P(no tiebreak in any of n sets)
    expected_sets = best_of - 0.5  # typical match length (rough)
    p_no_tb = (1 - p_tb_per_set) ** expected_sets
    p_tb = 1.0 - p_no_tb

    # Grass inflates tiebreaks significantly
    if surface == "grass":
        p_tb = min(0.90, p_tb * 1.25)
        p_no_tb = 1.0 - p_tb

    factors = [
        f"P(tiebreak per set): {p_tb_per_set:.0%}",
        f"Surface: {surface} — {'inflates' if surface == 'grass' else 'standard'} tiebreak rate",
    ]

    return {
        "probs": {"tiebreak": round(p_tb, 4), "no_tiebreak": round(p_no_tb, 4)},
        "factors": factors,
        "breakdown": {"Serve model": {"tiebreak": round(p_tb, 4), "no_tiebreak": round(p_no_tb, 4)}},
        "prop_description": "At Least One Tiebreak",
    }


# ── Sets Over / Under ─────────────────────────────────────────────────────────

def sets_over_under(p1: str, p2: str, surface: str = "hard",
                    p1_win_match = 0.55, best_of: int = 3,
                    threshold: float = 2.5) -> dict:
    p1_win_match = float(p1_win_match)
    """P(match goes over/under threshold sets). For BO3: 2 vs 3 sets. BO5: 3/4/5."""
    p1_hold = _serve_hold(p1, surface)
    p2_hold = _serve_hold(p2, surface)

    p1_set = _p_set(p1_hold, p2_hold)
    p1_set = 0.75 * p1_set + 0.25 * p1_win_match
    p2_set = 1 - p1_set

    if best_of == 3:
        # P(2-0 for either) + P(3 sets)
        p_2_sets = p1_set**2 + p2_set**2          # straight sets
        p_3_sets = 1.0 - p_2_sets                  # three sets

        if threshold <= 2.0:
            return {
                "probs": {"over_2": round(p_3_sets, 4), "under_2": round(p_2_sets, 4)},
                "factors": [f"P(straight sets): {p_2_sets:.0%}  P(3 sets): {p_3_sets:.0%}"],
                "breakdown": {"Set model": {"over_2": round(p_3_sets, 4), "under_2": round(p_2_sets, 4)}},
                "prop_description": f"Match Sets Over/Under {threshold}",
            }
        else:
            return {
                "probs": {"over_2.5": round(p_3_sets, 4), "under_2.5": round(p_2_sets, 4)},
                "factors": [f"P(straight sets): {p_2_sets:.0%}  P(3 sets): {p_3_sets:.0%}"],
                "breakdown": {"Set model": {}},
                "prop_description": f"Match Sets Over/Under {threshold}",
            }

    # Best-of-5
    p_3 = p1_set**3 + p2_set**3
    p_4 = 3 * (p1_set**2 * p2_set * p1_set + p2_set**2 * p1_set * p2_set)
    p_5 = 1.0 - p_3 - p_4

    over = p_4 + p_5 if threshold <= 3 else p_5
    under = 1.0 - over

    return {
        "probs": {"over": round(over, 4), "under": round(under, 4)},
        "factors": [f"P(3 sets): {p_3:.0%}  P(4): {p_4:.0%}  P(5): {p_5:.0%}"],
        "breakdown": {"Set model": {}},
        "prop_description": f"Match Sets Over/Under {threshold} (BO{best_of})",
    }
