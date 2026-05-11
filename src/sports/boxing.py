"""Boxing prediction handler."""
import json
import math
from pathlib import Path
from src.sports.base import AbstractSport, PredictionResult
from src.data import news, market
from src.models import elo as elo_module, calibrator
from src.market import edge as edge_mod, kelly as kelly_mod, odds as odds_mod

PLAYERS_FILE = Path(__file__).parent.parent.parent / "data" / "mappings" / "players.json"

BOXING_ELO = {
    "tyson fury": 1900, "oleksandr usyk": 1920, "anthony joshua": 1790,
    "canelo alvarez": 1880, "terence crawford": 1870, "errol spence": 1840,
    "deontay wilder": 1810, "david benavidez": 1820, "jermall charlo": 1790,
}


def _load_boxing_seeds() -> dict:
    try:
        return json.loads(PLAYERS_FILE.read_text()).get("boxing", {})
    except Exception:
        return {}


class BoxingPredictor(AbstractSport):

    sport_name = "boxing"
    sport_keywords = [
        "boxing", "fight", "bout", "wbc", "wba", "ibf", "wbo",
        "heavyweight boxing", "middleweight boxing", "welterweight boxing",
        "fury", "usyk", "joshua", "canelo", "crawford", "wilder",
        "ko", "knockout", "title fight", "world champion",
    ]

    def predict(self, entity1: str, entity2: str, date: str, context: dict) -> PredictionResult:
        sources = ["Seeded boxing ELO ratings"]

        seeds = _load_boxing_seeds()

        # 1. ELO
        elo_predictor = elo_module.EloPredictor(default_elo=1650)
        for name, elo in BOXING_ELO.items():
            elo_predictor.set(name, elo)
        for name, info in seeds.items():
            if "elo" in info:
                elo_predictor.set(name, info["elo"])

        f1_elo = elo_predictor.get(entity1.lower())
        f2_elo = elo_predictor.get(entity2.lower())
        elo_p1 = elo_module.win_probability(f1_elo, f2_elo)

        # 2. Style matchup heuristics (southpaw vs orthodox, reach, experience)
        style_adj = context.get("style_adjustment", 0.0)
        blended_p1 = max(0.05, min(0.95, elo_p1 + style_adj))

        # 3. News (injury, contract disputes, weight miss)
        f1_news = news.get_sentiment(entity1 + " boxing")
        f2_news = news.get_sentiment(entity2 + " boxing")
        all_flags = f1_news.get("flags", []) + f2_news.get("flags", [])

        sentiment_adj = (f1_news.get("score", 0) - f2_news.get("score", 0)) * 0.10
        blended_p1 = max(0.05, min(0.95, blended_p1 + sentiment_adj))

        probs = {"p1_win": round(blended_p1, 4), "p2_win": round(1 - blended_p1, 4)}

        # 4. Market
        mkt = market.get_market_odds(entity1, entity2, "boxing")
        market_mapped = None
        if mkt:
            market_mapped = {"p1_win": mkt.get("home_win"), "p2_win": mkt.get("away_win")}

        # 5. Edge + Kelly
        edges = edge_mod.calculate_edge(probs, market_mapped or {})
        best_outcome, best_info = edge_mod.best_bet(edges)
        best_edge = best_info["edge_pct"] if best_info else 0.0
        kelly_pct = 0.0
        if best_info and best_info["edge"] > 0:
            decimal = odds_mod.prob_to_decimal(best_info["market_prob"])
            kelly_pct = kelly_mod.kelly_fraction(best_info["model_prob"], decimal)

        factors = [
            f"ELO: {entity1} ({f1_elo:.0f}) vs {entity2} ({f2_elo:.0f})",
            f"Model probability: {entity1} {blended_p1*100:.1f}%",
        ]

        return PredictionResult(
            sport="Boxing",
            entity1=entity1,
            entity2=entity2,
            date=date,
            probabilities=probs,
            market_probs=market_mapped,
            edges=edges,
            best_bet=best_outcome,
            best_edge_pct=best_edge,
            kelly_stake_pct=kelly_pct,
            confidence=calibrator.confidence_score(probs),
            key_factors=factors,
            news_flags=all_flags[:5],
            data_sources=sources,
            model_breakdown={"ELO": {"p1_win": elo_p1}},
            competition=context.get("competition", "Boxing"),
        )
