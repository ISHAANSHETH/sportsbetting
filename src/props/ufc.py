"""UFC/Boxing prop calculators: method of victory, goes distance, round O/U."""
import math


# ── UFC Method of Victory ─────────────────────────────────────────────────────

def method_of_victory(f1_stats: dict, f2_stats: dict, winner_prob_f1: float) -> dict:
    """
    Compute P(f1 KO, f1 Sub, f1 Dec, f2 KO, f2 Sub, f2 Dec).
    Uses each fighter's historical finish rates modulated by the opponent's defense.
    """
    def finish_rates(stats: dict) -> tuple:
        total = max(1, stats.get("wins", 10))
        ko = stats.get("ko_wins", 3) / total
        sub = stats.get("sub_wins", 2) / total
        dec = stats.get("dec_wins", 5) / total
        # Normalise to sum to 1
        s = ko + sub + dec
        return ko/s, sub/s, dec/s

    f1_ko, f1_sub, f1_dec = finish_rates(f1_stats)
    f2_ko, f2_sub, f2_dec = finish_rates(f2_stats)

    # Opponent defense adjustment
    f1_str_def = f1_stats.get("str_def", 0.60)
    f2_str_def = f2_stats.get("str_def", 0.60)
    f1_td_def = f1_stats.get("td_def", 0.75)
    f2_td_def = f2_stats.get("td_def", 0.75)

    # f1 wins: their KO rate dampened by f2's striking defense
    f1_ko_adj = f1_ko * (1 - f2_str_def * 0.5)
    f1_sub_adj = f1_sub * (1 - f2_td_def * 0.4)
    f1_dec_adj = 1 - f1_ko_adj - f1_sub_adj

    # f2 wins: symmetric
    f2_ko_adj = f2_ko * (1 - f1_str_def * 0.5)
    f2_sub_adj = f2_sub * (1 - f1_td_def * 0.4)
    f2_dec_adj = 1 - f2_ko_adj - f2_sub_adj

    # Scale by win probability
    p_f2 = 1 - winner_prob_f1
    raw = {
        "f1_ko":  winner_prob_f1 * f1_ko_adj,
        "f1_sub": winner_prob_f1 * f1_sub_adj,
        "f1_dec": winner_prob_f1 * f1_dec_adj,
        "f2_ko":  p_f2 * f2_ko_adj,
        "f2_sub": p_f2 * f2_sub_adj,
        "f2_dec": p_f2 * f2_dec_adj,
    }
    total = sum(raw.values())
    probs = {k: round(v / total, 4) for k, v in raw.items()}

    factors = [
        f"F1 historical finishes — KO: {f1_ko*100:.0f}%  Sub: {f1_sub*100:.0f}%  Dec: {f1_dec*100:.0f}%",
        f"F2 historical finishes — KO: {f2_ko*100:.0f}%  Sub: {f2_sub*100:.0f}%  Dec: {f2_dec*100:.0f}%",
        f"F1 str_def: {f1_str_def:.0%}  F2 str_def: {f2_str_def:.0%}",
    ]

    return {
        "probs": probs,
        "factors": factors,
        "breakdown": {"Finish-rate model": {k: v for k, v in probs.items()}},
        "prop_description": "Method of Victory",
    }


def goes_distance(f1_stats: dict, f2_stats: dict) -> dict:
    """P(fight goes to judges' scorecards) vs P(finish)."""
    def dec_rate(stats: dict) -> float:
        total = max(1, stats.get("wins", 10))
        dec = stats.get("dec_wins", 5)
        return dec / total

    f1_dec_rate = dec_rate(f1_stats)
    f2_dec_rate = dec_rate(f2_stats)
    avg_dec = (f1_dec_rate + f2_dec_rate) / 2

    p_distance = min(0.92, max(0.08, avg_dec))
    p_finish = 1.0 - p_distance

    factors = [
        f"F1 decision rate: {f1_dec_rate*100:.0f}%  F2 decision rate: {f2_dec_rate*100:.0f}%",
    ]

    return {
        "probs": {"distance": round(p_distance, 4), "finish": round(p_finish, 4)},
        "factors": factors,
        "breakdown": {"Finish-rate model": {"distance": round(p_distance, 4), "finish": round(p_finish, 4)}},
        "prop_description": "Goes the Distance",
    }


def round_over_under(f1_stats: dict, f2_stats: dict, threshold: float,
                     total_rounds: int = 5) -> dict:
    """P(fight lasts > threshold rounds)."""
    # Estimate avg round of finish from finish rates
    f1_finish_rate = 1 - f1_stats.get("dec_wins", 5) / max(1, f1_stats.get("wins", 10))
    f2_finish_rate = 1 - f2_stats.get("dec_wins", 5) / max(1, f2_stats.get("wins", 10))
    avg_finish_rate_per_round = (f1_finish_rate + f2_finish_rate) / 2 / total_rounds

    # Survival probability: P(still going after r rounds)
    p_over = 1.0
    for r in range(1, int(threshold) + 1):
        p_over *= (1 - avg_finish_rate_per_round)

    # If threshold is X.5, this is already P(>X rounds)
    p_under = 1.0 - p_over

    return {
        "probs": {"over": round(p_over, 4), "under": round(p_under, 4)},
        "factors": [
            f"Avg finish rate/round: {avg_finish_rate_per_round*100:.1f}%",
            f"P(fight ends by round {int(threshold)}): {p_under*100:.1f}%",
        ],
        "breakdown": {"Round model": {"over": round(p_over, 4), "under": round(p_under, 4)}},
        "prop_description": f"Fight Over/Under {threshold} Rounds",
    }


# ── Boxing ────────────────────────────────────────────────────────────────────

def boxing_method(f1_stats: dict, f2_stats: dict, winner_prob_f1: float) -> dict:
    """KO/TKO vs Decision for boxing (no submission)."""
    def ko_rate(s: dict) -> float:
        total = max(1, s.get("wins", 10))
        return s.get("ko_wins", 5) / total

    f1_ko = ko_rate(f1_stats)
    f2_ko = ko_rate(f2_stats)

    p_f2 = 1 - winner_prob_f1
    raw = {
        "f1_ko":  winner_prob_f1 * f1_ko,
        "f1_dec": winner_prob_f1 * (1 - f1_ko),
        "f2_ko":  p_f2 * f2_ko,
        "f2_dec": p_f2 * (1 - f2_ko),
    }
    total = sum(raw.values())
    probs = {k: round(v / total, 4) for k, v in raw.items()}

    factors = [
        f"F1 KO rate: {f1_ko*100:.0f}%  F2 KO rate: {f2_ko*100:.0f}%",
    ]

    return {
        "probs": probs,
        "factors": factors,
        "breakdown": {"KO-rate model": {k: v for k, v in probs.items()}},
        "prop_description": "Method of Victory (Boxing)",
    }
