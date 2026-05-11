"""Football prop calculators: BTTS, over/under, player scorer, player foot/method."""
import math
from scipy.stats import poisson
from src.data.scrapers import player_stats as ps


# ── Helpers ─────────────────────────────────────────────────────────────────

def _expected_goals(home_data: dict, away_data: dict, is_neutral: bool = False) -> tuple:
    """Return (home_xg, away_xg) for the match."""
    home_xg = home_data.get("avg_xg") or home_data.get("avg_goals", 1.35)
    away_xg = away_data.get("avg_xg") or away_data.get("avg_goals", 1.10)
    if not is_neutral:
        home_xg *= 1.08   # home advantage bump
        away_xg *= 0.93
    return home_xg, away_xg


def _poisson_probs(home_xg: float, away_xg: float, max_goals: int = 10) -> dict:
    """P(home=i, away=j) for all i,j up to max_goals."""
    p = {}
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p[(i, j)] = poisson.pmf(i, home_xg) * poisson.pmf(j, away_xg)
    return p


# ── Over / Under ─────────────────────────────────────────────────────────────

def over_under_goals(home_data: dict, away_data: dict, threshold: float,
                     is_neutral: bool = False) -> dict:
    """Compute P(total goals > threshold) and P(total goals <= threshold)."""
    home_xg, away_xg = _expected_goals(home_data, away_data, is_neutral)
    joint = _poisson_probs(home_xg, away_xg)

    over_p = sum(p for (i, j), p in joint.items() if i + j > threshold)
    under_p = 1.0 - over_p

    factors = [
        f"Home xG: {home_xg:.2f}  Away xG: {away_xg:.2f}  Total expected: {home_xg + away_xg:.2f}",
        f"Threshold: {threshold} goals",
    ]
    if home_xg + away_xg > threshold + 0.3:
        factors.append(f"Both teams are high-scoring — leans Over")
    elif home_xg + away_xg < threshold - 0.3:
        factors.append("Defensive match expected — leans Under")

    return {
        "probs": {"over": round(over_p, 4), "under": round(under_p, 4)},
        "factors": factors,
        "breakdown": {
            "Dixon-Coles Poisson": {"over": round(over_p, 4), "under": round(under_p, 4)},
        },
        "prop_description": f"Over/Under {threshold} Goals",
    }


# ── BTTS ─────────────────────────────────────────────────────────────────────

def btts(home_data: dict, away_data: dict, is_neutral: bool = False) -> dict:
    """Both teams to score — Yes / No."""
    home_xg, away_xg = _expected_goals(home_data, away_data, is_neutral)

    p_home_blanks = poisson.pmf(0, home_xg)   # home fails to score
    p_away_blanks = poisson.pmf(0, away_xg)

    p_yes = (1 - p_home_blanks) * (1 - p_away_blanks)
    p_no = 1.0 - p_yes

    factors = [
        f"P(home scores): {(1-p_home_blanks)*100:.1f}%  P(away scores): {(1-p_away_blanks)*100:.1f}%",
        f"Home xG {home_xg:.2f} — Away xG {away_xg:.2f}",
    ]

    return {
        "probs": {"yes": round(p_yes, 4), "no": round(p_no, 4)},
        "factors": factors,
        "breakdown": {"Poisson": {"yes": round(p_yes, 4), "no": round(p_no, 4)}},
        "prop_description": "Both Teams To Score (BTTS)",
    }


# ── Player Anytime Scorer ─────────────────────────────────────────────────────

def player_anytime_scorer(player: str, team_data: dict, opp_data: dict,
                          is_neutral: bool = False) -> dict:
    """P(player scores >= 1 goal in the match)."""
    stats = ps.get_player_stats(player)
    xg_p90 = stats.get("xg_per_90", 0.30)
    minutes = stats.get("minutes_per_game", 75)

    # Opponent's defensive strength adjusts player xG
    opp_xga = opp_data.get("avg_xga") or opp_data.get("avg_conceded", 1.20)
    league_avg_xga = 1.20
    def_factor = opp_xga / league_avg_xga if league_avg_xga > 0 else 1.0
    def_factor = max(0.5, min(2.0, def_factor))

    match_xg = xg_p90 * (minutes / 90) * def_factor

    # P(scores 0) = e^(-xg)
    p_no_goal = math.exp(-match_xg)
    p_scores = 1.0 - p_no_goal

    factors = [
        f"{player}: {xg_p90:.2f} xG/90, avg {minutes:.0f} min/game",
        f"Match xG estimate: {match_xg:.2f} (opp def factor: {def_factor:.2f})",
        f"P(at least one goal): {p_scores*100:.1f}%",
    ]
    if stats.get("source") == "seeded":
        factors.append("Stats source: FBRef career data (seeded)")
    elif stats.get("source") == "fbref":
        factors.append("Stats source: FBRef live data")

    return {
        "probs": {"scores": round(p_scores, 4), "no_goal": round(p_no_goal, 4)},
        "factors": factors,
        "breakdown": {"Poisson(xG)": {"scores": round(p_scores, 4), "no_goal": round(p_no_goal, 4)}},
        "prop_description": f"{player} — Anytime Scorer",
        "player_stats": stats,
    }


# ── Player First Scorer ───────────────────────────────────────────────────────

def player_first_scorer(player: str, team_data: dict, opp_data: dict,
                        squad_size: int = 11) -> dict:
    """Rough P(player scores first goal) — P(scores) / expected scorers in team."""
    scorer_result = player_anytime_scorer(player, team_data, opp_data)
    p_scores = scorer_result["probs"]["scores"]

    team_xg = team_data.get("avg_xg") or team_data.get("avg_goals", 1.35)
    avg_scorers = max(1, team_xg * 0.7)  # roughly 0.7 different players per goal

    # P(first scorer) ≈ P(scores) * P(scores before teammates) — simplification
    p_first = p_scores / max(avg_scorers, 1.5)
    p_not_first = 1.0 - p_first

    factors = scorer_result["factors"] + [
        f"Team xG: {team_xg:.2f} — estimated goal-sharers: {avg_scorers:.1f}",
    ]

    return {
        "probs": {"first_scorer": round(p_first, 4), "not_first": round(p_not_first, 4)},
        "factors": factors,
        "breakdown": {"Model": {"first_scorer": round(p_first, 4), "not_first": round(p_not_first, 4)}},
        "prop_description": f"{player} — First Scorer",
    }


# ── Player Foot / Method Scorer ───────────────────────────────────────────────

def player_foot_scorer(player: str, foot: str, team_data: dict, opp_data: dict) -> dict:
    """P(player scores with [foot]) — P(scores) × P(goal is with foot | scores)."""
    stats = ps.get_player_stats(player)
    scorer_result = player_anytime_scorer(player, team_data, opp_data)
    p_scores = scorer_result["probs"]["scores"]

    # Foot split on goals ≈ shot split (a reasonable approximation)
    splits = stats.get("foot_splits", {"left": 0.35, "right": 0.55, "head": 0.10})
    foot_key = foot.lower().replace("_foot", "").replace(" foot", "")
    foot_share = splits.get(foot_key, splits.get("right", 0.55))

    p_foot_goal = p_scores * foot_share
    p_not = 1.0 - p_foot_goal

    dominant = stats.get("dominant_foot", "right")
    foot_label = f"{foot.title()} Foot" if foot.lower() in ("left", "right") else foot.title()

    factors = [
        f"{player}: {foot_share*100:.0f}% of shots taken with {foot_label}",
        f"Dominant foot: {dominant.title()}",
        f"P(scores): {p_scores*100:.1f}%  ×  P({foot_label}|scores): {foot_share*100:.0f}%",
    ]
    if splits == {"left": 0.35, "right": 0.55, "head": 0.10}:
        factors.append("⚠ No foot-split data for this player — using positional average")

    return {
        "probs": {f"{foot_key}_foot_goal": round(p_foot_goal, 4), "other": round(p_not, 4)},
        "factors": factors,
        "breakdown": {
            "Model": {f"{foot_key}_foot_goal": round(p_foot_goal, 4), "other": round(p_not, 4)}
        },
        "prop_description": f"{player} — Scores with {foot_label}",
    }


def player_header_scorer(player: str, team_data: dict, opp_data: dict) -> dict:
    """P(player scores with header)."""
    return player_foot_scorer(player, "head", team_data, opp_data)


# ── Player Assists ────────────────────────────────────────────────────────────

def player_assists(player: str, team_data: dict, opp_data: dict) -> dict:
    """P(player gets >= 1 assist)."""
    stats = ps.get_player_stats(player)
    ast_p90 = stats.get("assists_per_90", 0.20)
    minutes = stats.get("minutes_per_game", 75)

    # Adjust for opponent defensive strength
    opp_xga = opp_data.get("avg_xga") or opp_data.get("avg_conceded", 1.20)
    def_factor = min(1.5, max(0.6, opp_xga / 1.20))

    match_ast_xg = ast_p90 * (minutes / 90) * def_factor
    p_no_assist = math.exp(-match_ast_xg)
    p_assist = 1.0 - p_no_assist

    factors = [
        f"{player}: {ast_p90:.2f} assists/90, avg {minutes:.0f} min/game",
        f"Estimated match assist xG: {match_ast_xg:.2f}",
    ]

    return {
        "probs": {"assists": round(p_assist, 4), "no_assist": round(p_no_assist, 4)},
        "factors": factors,
        "breakdown": {"Poisson": {"assists": round(p_assist, 4), "no_assist": round(p_no_assist, 4)}},
        "prop_description": f"{player} — Assists (Anytime)",
    }


# ── Correct Score ─────────────────────────────────────────────────────────────

def correct_score(home_data: dict, away_data: dict, home_goals: int, away_goals: int,
                  is_neutral: bool = False) -> dict:
    """P(exact scoreline home_goals : away_goals)."""
    home_xg, away_xg = _expected_goals(home_data, away_data, is_neutral)

    p = poisson.pmf(home_goals, home_xg) * poisson.pmf(away_goals, away_xg)
    p_other = 1.0 - p

    return {
        "probs": {f"{home_goals}_{away_goals}": round(p, 4), "other": round(p_other, 4)},
        "factors": [
            f"Home xG: {home_xg:.2f}  Away xG: {away_xg:.2f}",
            f"P({home_goals}-{away_goals}): {p*100:.1f}%",
        ],
        "breakdown": {"Poisson": {f"{home_goals}_{away_goals}": round(p, 4)}},
        "prop_description": f"Correct Score {home_goals}–{away_goals}",
    }


# ── Half-time / Full-time ─────────────────────────────────────────────────────

def half_time_result(home_data: dict, away_data: dict, is_neutral: bool = False) -> dict:
    """Predict half-time result using half the expected goals."""
    home_xg, away_xg = _expected_goals(home_data, away_data, is_neutral)
    ht_home_xg = home_xg * 0.48   # slightly less than half — fewer goals in first half
    ht_away_xg = away_xg * 0.48

    joint = _poisson_probs(ht_home_xg, ht_away_xg, max_goals=5)
    ht_home_win = sum(p for (i, j), p in joint.items() if i > j)
    ht_draw = sum(p for (i, j), p in joint.items() if i == j)
    ht_away_win = sum(p for (i, j), p in joint.items() if j > i)

    return {
        "probs": {
            "ht_home_win": round(ht_home_win, 4),
            "ht_draw": round(ht_draw, 4),
            "ht_away_win": round(ht_away_win, 4),
        },
        "factors": [f"HT xG home: {ht_home_xg:.2f}  away: {ht_away_xg:.2f}"],
        "breakdown": {"Poisson(HT)": {"ht_home_win": round(ht_home_win, 4),
                                       "ht_draw": round(ht_draw, 4),
                                       "ht_away_win": round(ht_away_win, 4)}},
        "prop_description": "Half-Time Result",
    }
