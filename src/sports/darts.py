"""Darts and Badminton/Table Tennis prediction handler."""
import math
from src.sports.base import AbstractSport, PredictionResult
from src.data import news, market
from src.models import elo as elo_module, calibrator
from src.market import edge as edge_mod, kelly as kelly_mod, odds as odds_mod

# Darts player ELO seeds (PDC world ranking based)
DARTS_ELO = {
    "michael van gerwen": 1950, "mvg": 1950,
    "peter wright": 1840, "snakebite": 1840,
    "gerwyn price": 1820, "iceman": 1820,
    "jose de sousa": 1800, "special one": 1800,
    "jonny clayton": 1790, "ferret": 1790,
    "michael smith": 1860, "bully boy": 1860,
    "gary anderson": 1830, "the flying scotsman": 1830,
    "luke littler": 1870, "the nuke": 1870,
    "luke humphries": 1890, "cool hand luke": 1890,
    "dimitri van den bergh": 1780,
    "rob cross": 1810, "voltage": 1810,
}

# Badminton player ELO seeds (BWF world ranking based)
BADMINTON_ELO = {
    "viktor axelsen": 1920, "axelsen": 1920,
    "an se-young": 1900, "an se young": 1900,
    "carolina marin": 1850, "marin": 1850,
    "shi yuqi": 1870, "lee zii jia": 1830,
    "kunlavut vitidsarn": 1840,
    "chen yu fei": 1860,
    "akane yamaguchi": 1840, "yamaguchi": 1840,
    "tai tzu ying": 1820, "tai tzu-ying": 1820,
}

TABLE_TENNIS_ELO = {
    "fan zhendong": 1950, "ma long": 1930,
    "wang chuqin": 1910, "truls moregard": 1860,
    "felix lebrun": 1870, "alexis lebrun": 1850,
    "chen meng": 1920, "sun yingsha": 1910,
    "wang yidi": 1880, "mima ito": 1860,
}


class DartsPredictor(AbstractSport):

    sport_name = "darts"
    sport_keywords = [
        "darts", "pdc", "bdo", "world darts", "premier league darts",
        "van gerwen", "mvg", "wright", "price", "smith", "littler", "humphries",
        "world championship darts", "masters darts", "uk open",
    ]

    def predict(self, entity1: str, entity2: str, date: str, context: dict) -> PredictionResult:
        elo_predictor = elo_module.EloPredictor(default_elo=1700)
        for name, elo in DARTS_ELO.items():
            elo_predictor.set(name, elo)

        f1_elo = elo_predictor.get(entity1.lower())
        f2_elo = elo_predictor.get(entity2.lower())
        p1_win = elo_module.win_probability(f1_elo, f2_elo)

        f1_news = news.get_sentiment(entity1 + " darts")
        f2_news = news.get_sentiment(entity2 + " darts")
        all_flags = f1_news.get("flags", []) + f2_news.get("flags", [])
        sent_adj = (f1_news.get("score", 0) - f2_news.get("score", 0)) * 0.08
        p1_win = max(0.05, min(0.95, p1_win + sent_adj))

        probs = {"p1_win": round(p1_win, 4), "p2_win": round(1 - p1_win, 4)}
        mkt = market.get_market_odds(entity1, entity2, "darts")
        market_mapped = None
        if mkt:
            market_mapped = {"p1_win": mkt.get("home_win"), "p2_win": mkt.get("away_win")}

        edges = edge_mod.calculate_edge(probs, market_mapped or {})
        best_outcome, best_info = edge_mod.best_bet(edges)
        kelly_pct = 0.0
        if best_info and best_info["edge"] > 0:
            decimal = odds_mod.prob_to_decimal(best_info["market_prob"])
            kelly_pct = kelly_mod.kelly_fraction(best_info["model_prob"], decimal)

        return PredictionResult(
            sport="Darts",
            entity1=entity1, entity2=entity2, date=date,
            probabilities=probs, market_probs=market_mapped, edges=edges,
            best_bet=best_outcome,
            best_edge_pct=best_info["edge_pct"] if best_info else 0.0,
            kelly_stake_pct=kelly_pct,
            confidence=calibrator.confidence_score(probs),
            key_factors=[f"ELO: {entity1} ({f1_elo:.0f}) vs {entity2} ({f2_elo:.0f})"],
            news_flags=all_flags[:3],
            data_sources=["PDC ELO ratings"],
            model_breakdown={"ELO": {"p1_win": p1_win}},
            competition=context.get("competition", "Darts"),
        )


class BadmintonPredictor(AbstractSport):

    sport_name = "badminton"
    sport_keywords = [
        "badminton", "bwf", "all england", "thomas cup", "uber cup",
        "axelsen", "marin", "carolina", "shi yuqi", "vitidsarn",
        "table tennis", "ittf", "tt", "ping pong",
        "fan zhendong", "ma long", "wang chuqin", "chen meng",
    ]

    def predict(self, entity1: str, entity2: str, date: str, context: dict) -> PredictionResult:
        sport_label = "Table Tennis" if _is_table_tennis(entity1 + " " + entity2 + " " + context.get("competition", "")) else "Badminton"
        elo_seeds = TABLE_TENNIS_ELO if sport_label == "Table Tennis" else BADMINTON_ELO

        elo_predictor = elo_module.EloPredictor(default_elo=1700)
        for name, elo in elo_seeds.items():
            elo_predictor.set(name, elo)

        f1_elo = elo_predictor.get(entity1.lower())
        f2_elo = elo_predictor.get(entity2.lower())
        p1_win = elo_module.win_probability(f1_elo, f2_elo)

        f1_news = news.get_sentiment(entity1)
        f2_news = news.get_sentiment(entity2)
        all_flags = f1_news.get("flags", []) + f2_news.get("flags", [])
        sent_adj = (f1_news.get("score", 0) - f2_news.get("score", 0)) * 0.06
        p1_win = max(0.05, min(0.95, p1_win + sent_adj))

        probs = {"p1_win": round(p1_win, 4), "p2_win": round(1 - p1_win, 4)}
        mkt = market.get_market_odds(entity1, entity2, sport_label.lower())
        market_mapped = None
        if mkt:
            market_mapped = {"p1_win": mkt.get("home_win"), "p2_win": mkt.get("away_win")}

        edges = edge_mod.calculate_edge(probs, market_mapped or {})
        best_outcome, best_info = edge_mod.best_bet(edges)
        kelly_pct = 0.0
        if best_info and best_info["edge"] > 0:
            decimal = odds_mod.prob_to_decimal(best_info["market_prob"])
            kelly_pct = kelly_mod.kelly_fraction(best_info["model_prob"], decimal)

        return PredictionResult(
            sport=sport_label,
            entity1=entity1, entity2=entity2, date=date,
            probabilities=probs, market_probs=market_mapped, edges=edges,
            best_bet=best_outcome,
            best_edge_pct=best_info["edge_pct"] if best_info else 0.0,
            kelly_stake_pct=kelly_pct,
            confidence=calibrator.confidence_score(probs),
            key_factors=[f"ELO: {entity1} ({f1_elo:.0f}) vs {entity2} ({f2_elo:.0f})"],
            news_flags=all_flags[:3],
            data_sources=["BWF/ITTF ELO ratings"],
            model_breakdown={"ELO": {"p1_win": p1_win}},
            competition=context.get("competition", sport_label),
        )


def _is_table_tennis(text: str) -> bool:
    tt_keywords = ["table tennis", "ittf", "ping pong", "fan zhendong", "ma long", "wang chuqin", "tt "]
    return any(kw in text.lower() for kw in tt_keywords)
