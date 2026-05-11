"""FastAPI web server — serves the dashboard and prediction API."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import traceback

from dotenv import load_dotenv
load_dotenv()

from src import parser as query_parser
from src.sports.football import FootballPredictor
from src.sports.tennis import TennisPredictor
from src.sports.ufc import UFCPredictor
from src.sports.boxing import BoxingPredictor
from src.sports.cricket import CricketPredictor
from src.sports.darts import DartsPredictor, BadmintonPredictor

app = FastAPI(title="Sports Betting Predictor", version="1.0.0")

SPORT_HANDLERS = {
    "football": FootballPredictor(),
    "soccer": FootballPredictor(),
    "tennis": TennisPredictor(),
    "ufc": UFCPredictor(),
    "mma": UFCPredictor(),
    "boxing": BoxingPredictor(),
    "cricket": CricketPredictor(),
    "darts": DartsPredictor(),
    "badminton": BadmintonPredictor(),
    "table tennis": BadmintonPredictor(),
}

SUPPORTED_SPORTS = [
    {"sport": "Football / Soccer", "emoji": "⚽", "accuracy": "~63%", "source": "FBRef, Understat, ESPN", "tip": "Dixon-Coles xG model"},
    {"sport": "Tennis", "emoji": "🎾", "accuracy": "~68%", "source": "Jeff Sackmann ATP/WTA", "tip": "Surface ELO + serve stats"},
    {"sport": "UFC / MMA", "emoji": "🥊", "accuracy": "~63%", "source": "UFCStats.com", "tip": "Strike/grapple differentials"},
    {"sport": "Boxing", "emoji": "🥊", "accuracy": "~62%", "source": "BoxRec, Tapology", "tip": "ELO + style matchups"},
    {"sport": "Cricket", "emoji": "🏏", "accuracy": "~66%", "source": "CricSheet ball-by-ball", "tip": "Batting/bowling averages"},
    {"sport": "Darts", "emoji": "🎯", "accuracy": "~67%", "source": "PDC rankings", "tip": "Most consistent sport"},
    {"sport": "Badminton", "emoji": "🏸", "accuracy": "~64%", "source": "BWF world rankings", "tip": "1v1 ELO very predictive"},
    {"sport": "Table Tennis", "emoji": "🏓", "accuracy": "~64%", "source": "ITTF rankings", "tip": "Consistent, high data"},
]

EXAMPLE_QUERIES = [
    "Portugal vs Spain Nations League",
    "Over 2.5 goals Arsenal vs Liverpool",
    "BTTS Barcelona vs Real Madrid",
    "Will Haaland score vs Real Madrid",
    "Will Neymar score with his left foot vs Brazil",
    "Djokovic vs Alcaraz — first set Wimbledon",
    "Djokovic vs Alcaraz — tiebreak Wimbledon",
    "Jon Jones vs Stipe Miocic — wins by KO",
    "Jon Jones vs Stipe Miocic — goes the distance",
    "Tyson Fury vs Oleksandr Usyk method of victory boxing",
    "India vs Australia over 350 runs T20 World Cup",
    "Rohit Sharma top scorer vs England",
]


class PredictRequest(BaseModel):
    query: str


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/api/sports")
async def get_sports():
    return {"sports": SUPPORTED_SPORTS, "examples": EXAMPLE_QUERIES}


@app.post("/api/predict")
async def predict(req: PredictRequest):
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    parsed = query_parser.parse(query)

    if "error" in parsed:
        raise HTTPException(status_code=422, detail=parsed["error"])

    if "command" in parsed:
        return {"command": parsed["command"], "sports": SUPPORTED_SPORTS}

    entity1 = parsed["entity1"]
    entity2 = parsed["entity2"]
    sport = parsed["sport"]
    date = parsed["date"]
    context = {
        "competition": parsed.get("competition", ""),
        "is_neutral": parsed.get("is_neutral", False),
        "venue": parsed.get("venue", ""),
    }

    handler = SPORT_HANDLERS.get(sport)
    if not handler:
        raise HTTPException(status_code=422, detail=f"Sport '{sport}' not supported")

    bet_type = parsed.get("bet_type", "match_result")
    prop_params = parsed.get("prop_params", {})
    prop_player = parsed.get("prop_player", "")

    try:
        from src.predictor import _predict_prop
        if bet_type == "match_result":
            result = handler.predict(entity1, entity2, date, context)
        else:
            result = _predict_prop(
                sport, entity1, entity2, date, context,
                bet_type, prop_params, prop_player, handler,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

    return _serialize(result, sport)


def _serialize(result, sport: str) -> dict:
    """Convert PredictionResult to JSON-serializable dict."""
    outcome_labels = _outcome_labels(result.entity1, result.entity2, result.probabilities)

    outcomes = []
    for key, prob in result.probabilities.items():
        if prob is None:
            continue
        edge_info = (result.edges or {}).get(key, {})
        market_prob = (result.market_probs or {}).get(key)
        outcomes.append({
            "key": key,
            "label": outcome_labels.get(key, key),
            "model_prob": round(prob * 100, 1),
            "market_prob": round(market_prob * 100, 1) if market_prob is not None else None,
            "edge_pct": edge_info.get("edge_pct"),
            "edge_rating": edge_info.get("rating"),
            "is_best_bet": key == result.best_bet,
        })

    return {
        "sport": result.sport,
        "entity1": result.entity1,
        "entity2": result.entity2,
        "date": result.date,
        "competition": result.competition,
        "venue": result.venue,
        "outcomes": outcomes,
        "best_bet": result.best_bet,
        "best_bet_label": outcome_labels.get(result.best_bet) if result.best_bet else None,
        "best_edge_pct": result.best_edge_pct,
        "kelly_stake_pct": result.kelly_stake_pct,
        "confidence": result.confidence,
        "key_factors": result.key_factors,
        "news_flags": result.news_flags,
        "data_sources": result.data_sources,
        "has_market": result.market_probs is not None,
        "bet_type": getattr(result, "bet_type", "match_result"),
        "prop_description": getattr(result, "prop_description", ""),
        "prop_player": getattr(result, "prop_player", ""),
        "model_breakdown": {
            k: {kk: round(vv * 100, 1) for kk, vv in v.items()} if v else {}
            for k, v in (result.model_breakdown or {}).items()
        },
    }


def _outcome_labels(e1: str, e2: str, probs: dict) -> dict:
    _PROP = {
        "over": "Over", "under": "Under",
        "yes": "Yes (BTTS)", "no": "No (BTTS)",
        "scores": "Scores", "no_goal": "No Goal",
        "assists": "Assists", "no_assist": "No Assist",
        "first_scorer": "First Scorer", "not_first": "Not First",
        "top_scorer": "Top Scorer", "not_top": "Not Top Scorer",
        "distance": "Goes Distance", "finish": "Stopped Early",
        "tiebreak": "Tiebreak", "no_tiebreak": "No Tiebreak",
        "p1_set1": e1, "p2_set1": e2,
        "ht_home_win": f"HT: {e1}", "ht_draw": "HT: Draw", "ht_away_win": f"HT: {e2}",
        "f1_ko": f"{e1} KO/TKO", "f1_sub": f"{e1} Sub", "f1_dec": f"{e1} Decision",
        "f2_ko": f"{e2} KO/TKO", "f2_sub": f"{e2} Sub", "f2_dec": f"{e2} Decision",
        "left_foot_goal": "Left Foot Goal", "right_foot_goal": "Right Foot Goal",
        "head_goal": "Header Goal", "other": "Other / No",
    }
    labels = {}
    for key in probs:
        if key in ("home_win", "p1_win", "f1_win"):
            labels[key] = e1
        elif key in ("away_win", "p2_win", "f2_win"):
            labels[key] = e2
        elif key == "draw":
            labels[key] = "Draw"
        elif key in _PROP:
            labels[key] = _PROP[key]
        else:
            labels[key] = key.replace("_", " ").title()
    return labels


# Mount static files last so API routes take priority
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
