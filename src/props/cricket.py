"""Cricket prop calculators: runs O/U, top batsman, wickets O/U."""
import math

# Seeded scoring rates by format (runs per over)
FORMAT_RATES = {
    "t20":   {"runs_per_over": 8.5,  "total_overs": 20},
    "t20i":  {"runs_per_over": 8.2,  "total_overs": 20},
    "odi":   {"runs_per_over": 5.8,  "total_overs": 50},
    "test":  {"runs_per_over": 3.2,  "total_overs": 90},
    "ipl":   {"runs_per_over": 8.8,  "total_overs": 20},
}

TEAM_BATTING_SEEDS = {
    "india":       {"t20": 9.1, "odi": 6.1, "test": 3.4, "batting_avg": 32},
    "australia":   {"t20": 8.6, "odi": 5.9, "test": 3.5, "batting_avg": 31},
    "england":     {"t20": 8.8, "odi": 6.2, "test": 3.6, "batting_avg": 30},
    "south africa":{"t20": 8.4, "odi": 5.7, "test": 3.2, "batting_avg": 28},
    "new zealand": {"t20": 8.0, "odi": 5.6, "test": 3.3, "batting_avg": 29},
    "pakistan":    {"t20": 8.3, "odi": 5.5, "test": 3.1, "batting_avg": 27},
    "west indies": {"t20": 8.9, "odi": 5.4, "test": 3.0, "batting_avg": 26},
    "sri lanka":   {"t20": 8.1, "odi": 5.3, "test": 3.0, "batting_avg": 26},
    "bangladesh":  {"t20": 7.8, "odi": 4.9, "test": 2.7, "batting_avg": 23},
    "afghanistan": {"t20": 7.9, "odi": 4.7, "test": 2.5, "batting_avg": 22},
}

PLAYER_BATTING_SEEDS = {
    "virat kohli":    {"batting_avg": 48, "sr_t20": 142, "sr_odi": 93, "centuries": 80},
    "rohit sharma":   {"batting_avg": 45, "sr_t20": 140, "sr_odi": 90, "centuries": 48},
    "babar azam":     {"batting_avg": 43, "sr_t20": 130, "sr_odi": 88, "centuries": 30},
    "steve smith":    {"batting_avg": 58, "sr_t20": 125, "sr_odi": 84, "centuries": 32},
    "joe root":       {"batting_avg": 55, "sr_t20": 120, "sr_odi": 86, "centuries": 35},
    "kane williamson":{"batting_avg": 53, "sr_t20": 128, "sr_odi": 87, "centuries": 24},
    "david warner":   {"batting_avg": 44, "sr_t20": 143, "sr_odi": 91, "centuries": 22},
    "shubman gill":   {"batting_avg": 46, "sr_t20": 145, "sr_odi": 95, "centuries": 12},
    "ben stokes":     {"batting_avg": 37, "sr_t20": 133, "sr_odi": 95, "centuries": 14},
    "pat cummins":    {"batting_avg": 23, "sr_t20": 120, "sr_odi": 76, "centuries": 1},
}


def _detect_format(context: dict) -> str:
    comp = (context.get("competition", "") + " " + context.get("venue", "")).lower()
    if "t20" in comp or "ipl" in comp or "twenty" in comp:
        return "t20"
    if "odi" in comp or "one day" in comp:
        return "odi"
    if "test" in comp:
        return "test"
    return "t20"


def runs_over_under(team1: str, team2: str, threshold: float, context: dict) -> dict:
    """P(total runs scored > threshold) in the match."""
    fmt = _detect_format(context)
    seed1 = TEAM_BATTING_SEEDS.get(team1.lower(), {})
    seed2 = TEAM_BATTING_SEEDS.get(team2.lower(), {})

    rate1 = seed1.get(fmt, FORMAT_RATES.get(fmt, {}).get("runs_per_over", 8.0))
    rate2 = seed2.get(fmt, FORMAT_RATES.get(fmt, {}).get("runs_per_over", 8.0))
    overs = FORMAT_RATES.get(fmt, {}).get("total_overs", 20)

    expected_runs_t1 = rate1 * overs
    expected_runs_t2 = rate2 * overs
    total_expected = expected_runs_t1 + expected_runs_t2

    # Use a normal distribution approximation for total runs
    # Std dev: roughly 12% of expected in T20, higher in test
    std_factor = {"t20": 0.12, "odi": 0.10, "test": 0.18}.get(fmt, 0.12)
    std = total_expected * std_factor

    # P(over) using normal CDF approximation
    from math import erf, sqrt
    z = (threshold - total_expected) / (std * sqrt(2))
    p_over = (1 - erf(z)) / 2
    p_under = 1.0 - p_over

    factors = [
        f"{team1} expected runs ({fmt.upper()}): {expected_runs_t1:.0f}",
        f"{team2} expected runs: {expected_runs_t2:.0f}",
        f"Total expected: {total_expected:.0f} vs threshold: {threshold}",
    ]

    return {
        "probs": {"over": round(p_over, 4), "under": round(p_under, 4)},
        "factors": factors,
        "breakdown": {"Normal approx": {"over": round(p_over, 4), "under": round(p_under, 4)}},
        "prop_description": f"Runs Over/Under {threshold} ({fmt.upper()})",
    }


def player_over_under_runs(player: str, threshold: float, context: dict) -> dict:
    """P(player scores > threshold runs in their innings)."""
    fmt = _detect_format(context)
    stats = None
    for seed_name, s in PLAYER_BATTING_SEEDS.items():
        if seed_name in player.lower() or player.lower() in seed_name:
            stats = s
            break

    if stats is None:
        # Generic
        avg = TEAM_BATTING_SEEDS.get("india", {}).get("batting_avg", 28) * 0.7
        stats = {"batting_avg": avg}

    avg = stats.get("batting_avg", 30)
    # T20 scores compress the batting avg
    fmt_factor = {"t20": 0.7, "odi": 0.85, "test": 1.0}.get(fmt, 0.7)
    expected = avg * fmt_factor
    std = expected * 0.65  # batting scores are highly variable

    from math import erf, sqrt
    z = (threshold - expected) / (std * sqrt(2))
    p_over = (1 - erf(z)) / 2
    p_under = 1.0 - p_over

    factors = [
        f"{player} batting avg: {avg:.0f}  Format adj: ×{fmt_factor}",
        f"Expected runs this innings: {expected:.0f}  vs threshold: {threshold}",
    ]

    return {
        "probs": {"over": round(p_over, 4), "under": round(p_under, 4)},
        "factors": factors,
        "breakdown": {"Normal model": {"over": round(p_over, 4), "under": round(p_under, 4)}},
        "prop_description": f"{player} Over/Under {threshold} Runs",
    }


def top_scorer(player: str, team: str, context: dict) -> dict:
    """P(player is top scorer for their team)."""
    seed = None
    for seed_name, s in PLAYER_BATTING_SEEDS.items():
        if seed_name in player.lower() or player.lower() in seed_name:
            seed = s
            break

    team_seed = TEAM_BATTING_SEEDS.get(team.lower(), {})
    avg = (seed or {}).get("batting_avg", 28)
    team_avg = team_seed.get("batting_avg", 26)

    # P(top scorer) approximation based on batting avg relative to team
    rel_strength = avg / max(team_avg, 1)
    # Typically 11 batters, but top 5 actually score most
    p_top = min(0.60, max(0.10, rel_strength / 3.5))

    factors = [
        f"{player} batting avg: {avg}  Team avg: {team_avg}",
        f"Relative strength index: {rel_strength:.2f}",
    ]

    return {
        "probs": {"top_scorer": round(p_top, 4), "not_top": round(1 - p_top, 4)},
        "factors": factors,
        "breakdown": {"Avg model": {"top_scorer": round(p_top, 4), "not_top": round(1 - p_top, 4)}},
        "prop_description": f"{player} — Top Scorer for {team}",
    }
