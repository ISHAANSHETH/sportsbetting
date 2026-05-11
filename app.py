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
    "Djokovic vs Alcaraz Wimbledon",
    "Jon Jones vs Stipe Miocic UFC",
    "India vs Australia T20 World Cup",
    "Tyson Fury vs Oleksandr Usyk boxing",
    "Michael van Gerwen vs Luke Humphries PDC",
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

    try:
        result = handler.predict(entity1, entity2, date, context)
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
        "model_breakdown": {
            k: {kk: round(vv * 100, 1) for kk, vv in v.items()} if v else {}
            for k, v in (result.model_breakdown or {}).items()
        },
    }


def _outcome_labels(e1: str, e2: str, probs: dict) -> dict:
    labels = {}
    for key in probs:
        if key in ("home_win", "p1_win", "f1_win"):
            labels[key] = e1
        elif key in ("away_win", "p2_win", "f2_win"):
            labels[key] = e2
        elif key == "draw":
            labels[key] = "Draw"
        else:
            labels[key] = key.replace("_", " ").title()
    return labels


# Mount static files last so API routes take priority
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
