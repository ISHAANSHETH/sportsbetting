"""Main orchestrator — routes parsed query to the correct sport handler or prop calculator."""
from typing import Optional
from src import parser as query_parser
from src.sports.football import FootballPredictor
from src.sports.tennis import TennisPredictor
from src.sports.ufc import UFCPredictor
from src.sports.boxing import BoxingPredictor
from src.sports.cricket import CricketPredictor
from src.sports.darts import DartsPredictor, BadmintonPredictor
from src.display import terminal
from src.sports.base import PredictionResult


SPORT_HANDLERS = {
    "football": FootballPredictor(),
    "soccer":   FootballPredictor(),
    "tennis":   TennisPredictor(),
    "ufc":      UFCPredictor(),
    "mma":      UFCPredictor(),
    "boxing":   BoxingPredictor(),
    "cricket":  CricketPredictor(),
    "darts":    DartsPredictor(),
    "badminton":BadmintonPredictor(),
    "table tennis": BadmintonPredictor(),
}


def run(query: str) -> None:
    predict_query(query)


def predict_query(query: str) -> Optional[PredictionResult]:
    """Parse query, run prediction, render result. Returns PredictionResult or None."""
    parsed = query_parser.parse(query)

    if "command" in parsed:
        if parsed["command"] == "show_sports":
            terminal.render_sports_list()
        elif parsed["command"] == "help":
            _show_help()
        return None

    if "error" in parsed:
        terminal.render_error(parsed["error"])
        return None

    entity1 = parsed["entity1"]
    entity2 = parsed["entity2"]
    sport = parsed["sport"]
    date = parsed["date"]
    bet_type = parsed.get("bet_type", "match_result")
    prop_params = parsed.get("prop_params", {})
    prop_player = parsed.get("prop_player", "")

    context = {
        "competition": parsed.get("competition", ""),
        "is_neutral": parsed.get("is_neutral", False),
        "venue": parsed.get("venue", ""),
    }

    handler = SPORT_HANDLERS.get(sport)
    if not handler:
        terminal.render_error(f"Sport '{sport}' is not yet supported.")
        return None

    if bet_type == "match_result":
        label = f"{entity1} vs {entity2} ({sport.title()})"
    else:
        pp = prop_player or entity1
        label = f"{pp} prop — {bet_type.replace('_', ' ')} ({sport.title()})"
    terminal.console.print(f"\n[dim]Analyzing {label}...[/dim]")

    try:
        if bet_type == "match_result":
            result = handler.predict(entity1, entity2, date, context)
        else:
            result = _predict_prop(
                sport, entity1, entity2, date, context,
                bet_type, prop_params, prop_player, handler,
            )
        terminal.render(result)
        return result
    except Exception as e:
        terminal.render_error(f"Prediction failed: {e}")
        return None


def _predict_prop(sport: str, entity1: str, entity2: str, date: str,
                  context: dict, bet_type: str, prop_params: dict,
                  prop_player: str, handler) -> PredictionResult:
    """Route to the correct prop calculator and wrap into PredictionResult."""
    from src.data import market as mkt_mod
    from src.market import edge as edge_mod, kelly as kelly_mod

    # ── Fetch base data needed by most prop calculators ────────────────────
    home_data = away_data = {}
    f1_stats = f2_stats = {}
    p1_win_prob = 0.5

    if sport in ("football", "soccer"):
        from src.data.scrapers import fbref
        home_data = fbref.get_team_data(entity1)
        away_data = fbref.get_team_data(entity2)
        # Quick match-level win probability for context
        match_result = handler.predict(entity1, entity2, date, context)
        p1_win_prob = match_result.probabilities.get("home_win", 0.5)

    elif sport in ("ufc", "mma", "boxing"):
        from src.data.scrapers import ufcstats
        f1_stats = ufcstats.get_fighter_stats(entity1)
        f2_stats = ufcstats.get_fighter_stats(entity2)
        match_result = handler.predict(entity1, entity2, date, context)
        p1_win_prob = match_result.probabilities.get(
            "p1_win", match_result.probabilities.get("f1_win", 0.5)
        )

    elif sport == "tennis":
        match_result = handler.predict(entity1, entity2, date, context)
        p1_win_prob = match_result.probabilities.get("p1_win", 0.5)

    elif sport == "cricket":
        match_result = handler.predict(entity1, entity2, date, context)
        p1_win_prob = match_result.probabilities.get("p1_win", 0.5)

    # ── Dispatch to prop calculators ───────────────────────────────────────
    calc = _dispatch_prop(
        sport, bet_type, prop_params, prop_player,
        entity1, entity2, context,
        home_data, away_data, f1_stats, f2_stats, p1_win_prob,
    )

    probs = calc["probs"]
    prop_desc = calc.get("prop_description", bet_type.replace("_", " ").title())
    factors = calc.get("factors", [])
    breakdown = calc.get("breakdown", {})

    # ── Market comparison ──────────────────────────────────────────────────
    market_probs = mkt_mod.get_prop_market_odds(
        entity1, entity2, bet_type, prop_params, prop_player
    )

    edges = {}
    best_bet = None
    best_edge = 0.0
    if market_probs:
        for k, model_p in probs.items():
            mkt_p = market_probs.get(k)
            if mkt_p is not None and mkt_p > 0.01:
                edge_info = edge_mod.calculate_edge(model_p, mkt_p)
                edges[k] = edge_info
                if edge_info["edge_pct"] > best_edge:
                    best_edge = edge_info["edge_pct"]
                    best_bet = k
    else:
        # No market — pick best probability
        best_bet = max(probs, key=lambda k: probs[k])
        best_edge = 0.0

    kelly = kelly_mod.kelly_stake(best_edge / 100) if best_edge > 0 else 0.0

    return PredictionResult(
        sport=sport.title(),
        entity1=entity1,
        entity2=entity2,
        date=date,
        probabilities=probs,
        market_probs=market_probs,
        edges=edges,
        best_bet=best_bet,
        best_edge_pct=best_edge,
        kelly_stake_pct=kelly,
        confidence=70.0,
        key_factors=factors,
        news_flags=[],
        data_sources=calc.get("sources", ["Model"]),
        model_breakdown=breakdown,
        competition=context.get("competition", ""),
        venue=context.get("venue", "Unknown"),
        is_neutral=context.get("is_neutral", False),
        bet_type=bet_type,
        prop_description=prop_desc,
        prop_player=prop_player,
    )


def _dispatch_prop(sport: str, bet_type: str, prop_params: dict, prop_player: str,
                   e1: str, e2: str, context: dict,
                   home_data: dict, away_data: dict,
                   f1_stats: dict, f2_stats: dict, p1_win: float) -> dict:
    is_neutral = context.get("is_neutral", False)

    # ── Football props ─────────────────────────────────────────────────────
    if sport in ("football", "soccer"):
        from src.props import football as fp

        if bet_type == "over_under":
            threshold = prop_params.get("threshold", 2.5)
            return fp.over_under_goals(home_data, away_data, threshold, is_neutral)

        if bet_type == "btts":
            return fp.btts(home_data, away_data, is_neutral)

        if bet_type in ("player_scorer", "player_first_scorer") and prop_player:
            if bet_type == "player_first_scorer":
                return fp.player_first_scorer(prop_player, home_data, away_data)
            return fp.player_anytime_scorer(prop_player, home_data, away_data, is_neutral)

        if bet_type == "player_foot" and prop_player:
            foot = prop_params.get("foot", "right")
            return fp.player_foot_scorer(prop_player, foot, home_data, away_data)

        if bet_type == "player_header" and prop_player:
            return fp.player_header_scorer(prop_player, home_data, away_data)

        if bet_type == "player_assists" and prop_player:
            return fp.player_assists(prop_player, home_data, away_data)

        if bet_type == "half_time":
            return fp.half_time_result(home_data, away_data, is_neutral)

        if bet_type == "correct_score":
            hg = prop_params.get("home_goals", 1)
            ag = prop_params.get("away_goals", 1)
            return fp.correct_score(home_data, away_data, hg, ag, is_neutral)

        # Fallback — over/under 2.5
        return fp.over_under_goals(home_data, away_data, 2.5, is_neutral)

    # ── UFC / Boxing props ─────────────────────────────────────────────────
    if sport in ("ufc", "mma"):
        from src.props import ufc as up

        if bet_type == "method_victory":
            return up.method_of_victory(f1_stats, f2_stats, p1_win)

        if bet_type == "goes_distance":
            return up.goes_distance(f1_stats, f2_stats)

        if bet_type == "over_under":
            threshold = prop_params.get("threshold", 2.5)
            total_rounds = 5
            return up.round_over_under(f1_stats, f2_stats, threshold, total_rounds)

        return up.method_of_victory(f1_stats, f2_stats, p1_win)

    if sport == "boxing":
        from src.props import ufc as up

        if bet_type == "method_victory":
            return up.boxing_method(f1_stats, f2_stats, p1_win)

        if bet_type == "goes_distance":
            return up.goes_distance(f1_stats, f2_stats)

        if bet_type == "over_under":
            threshold = prop_params.get("threshold", 10.5)
            return up.round_over_under(f1_stats, f2_stats, threshold, total_rounds=12)

        return up.boxing_method(f1_stats, f2_stats, p1_win)

    # ── Tennis props ──────────────────────────────────────────────────────
    if sport == "tennis":
        from src.props import tennis as tp
        surface = _detect_surface(context)

        if bet_type == "tennis_first_set":
            return tp.first_set_winner(e1, e2, surface, p1_win)

        if bet_type == "tennis_tiebreak":
            best_of = 5 if any(x in context.get("competition", "").lower()
                               for x in ["grand slam", "wimbledon", "us open", "french", "australian"]) else 3
            return tp.tiebreak_in_match(e1, e2, surface, best_of)

        if bet_type == "over_under":
            threshold = prop_params.get("threshold", 2.5)
            best_of = 5 if any(x in context.get("competition", "").lower()
                               for x in ["grand slam", "wimbledon", "us open", "french", "australian"]) else 3
            return tp.sets_over_under(e1, e2, surface, p1_win, best_of, threshold)

        # Default — first set
        return tp.first_set_winner(e1, e2, surface, p1_win)

    # ── Cricket props ─────────────────────────────────────────────────────
    if sport == "cricket":
        from src.props import cricket as cp

        if bet_type == "over_under":
            threshold = prop_params.get("threshold", 350)
            return cp.runs_over_under(e1, e2, threshold, context)

        if bet_type == "cricket_top_bat":
            player = prop_player or e1
            return cp.top_scorer(player, e1, context)

        if bet_type == "cricket_century" and prop_player:
            return cp.player_over_under_runs(prop_player, 100, context)

        return cp.runs_over_under(e1, e2, 150, context)

    # ── Darts / Badminton / Table Tennis ─────────────────────────────────
    if bet_type == "over_under":
        threshold = prop_params.get("threshold", 2.5)
        # Simple — use match win probability to estimate set/leg O/U
        p_over = max(0.3, min(0.7, abs(p1_win - 0.5) * -2 + 0.65))
        return {
            "probs": {"over": round(p_over, 4), "under": round(1 - p_over, 4)},
            "factors": [f"Estimated from match win probability: {p1_win:.0%}"],
            "breakdown": {},
            "prop_description": f"Over/Under {threshold}",
        }

    return {
        "probs": {"yes": 0.5, "no": 0.5},
        "factors": ["Insufficient data for this prop type"],
        "breakdown": {},
        "prop_description": bet_type.replace("_", " ").title(),
    }


def _detect_surface(context: dict) -> str:
    venue = (context.get("venue", "") + " " + context.get("competition", "")).lower()
    if any(k in venue for k in ["clay", "roland garros", "french", "madrid", "rome", "barcelona"]):
        return "clay"
    if any(k in venue for k in ["grass", "wimbledon", "queen", "halle"]):
        return "grass"
    return "hard"


def _show_help():
    from rich.console import Console
    from rich.padding import Padding
    from rich.text import Text
    c = Console()
    c.print("\n[bold]EdgeFinder — Sports Betting Predictor[/bold]")
    c.print(Padding(Text(
        "Match result:\n"
        '  "Portugal vs Spain Nations League"\n'
        '  "Djokovic vs Alcaraz Wimbledon tomorrow"\n\n'
        "Prop bets:\n"
        '  "Over 2.5 goals Portugal vs Spain"\n'
        '  "BTTS Arsenal vs Liverpool"\n'
        '  "Will Neymar score vs Brazil"\n'
        '  "Will Neymar score with his left foot vs Brazil"\n'
        '  "Haaland anytime scorer vs Real Madrid"\n'
        '  "Jon Jones vs Stipe Miocic — wins by KO"\n'
        '  "Jon Jones vs Stipe Miocic — goes the distance"\n'
        '  "Djokovic vs Alcaraz — first set"\n'
        '  "Djokovic vs Alcaraz — tiebreak Wimbledon"\n'
        '  "Over 2.5 sets Djokovic vs Alcaraz"\n'
        '  "Fury vs Usyk — over 10.5 rounds"\n'
        '  "India vs Australia — over 350 runs T20"\n\n'
        "Other commands:\n"
        '  trades / settle <id> / sports / exit',
        style="dim",
    ), (0, 2)))
