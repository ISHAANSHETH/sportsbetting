"""Trade log — persist bets to data/trades.json and compute P&L."""
import json
import os
import uuid
from datetime import datetime
from typing import Optional

_TRADES_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "trades.json")


def _path() -> str:
    os.makedirs(os.path.dirname(_TRADES_FILE), exist_ok=True)
    return os.path.abspath(_TRADES_FILE)


def load() -> list:
    p = _path()
    if not os.path.exists(p):
        return []
    with open(p) as f:
        return json.load(f)


def save(trades: list) -> None:
    with open(_path(), "w") as f:
        json.dump(trades, f, indent=2)


def log(
    result,
    bet_outcome: str,
    bet_label: str,
    stake: float,
    odds: Optional[float],
) -> dict:
    """Add a new pending trade from a PredictionResult."""
    edge_info = (result.edges or {}).get(bet_outcome, {})
    model_prob = (result.probabilities or {}).get(bet_outcome)
    market_prob = (result.market_probs or {}).get(bet_outcome) if result.market_probs else None

    trade = {
        "id": uuid.uuid4().hex[:8],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "sport": result.sport,
        "entity1": result.entity1,
        "entity2": result.entity2,
        "competition": result.competition or "",
        "date": result.date,
        "bet_outcome": bet_outcome,
        "bet_label": bet_label,
        "model_prob": round(model_prob * 100, 1) if model_prob is not None else None,
        "market_prob": round(market_prob * 100, 1) if market_prob is not None else None,
        "edge_pct": edge_info.get("edge_pct"),
        "kelly_stake_pct": result.kelly_stake_pct,
        "stake": stake,
        "odds": odds,
        "status": "pending",
        "pnl": None,
    }

    trades = load()
    trades.append(trade)
    save(trades)
    return trade


def settle(trade_id: str, won: bool) -> Optional[dict]:
    """Mark a trade as won or lost and compute P&L."""
    trades = load()
    for t in trades:
        if t["id"] == trade_id:
            t["status"] = "won" if won else "lost"
            stake = t["stake"]
            odds = t.get("odds")
            if won:
                t["pnl"] = round(stake * (odds - 1), 2) if odds else stake
            else:
                t["pnl"] = -stake
            save(trades)
            return t
    return None


def stats(trades: list) -> dict:
    settled = [t for t in trades if t["status"] in ("won", "lost")]
    won = [t for t in settled if t["status"] == "won"]
    total_stake = sum(t["stake"] for t in settled if t["stake"])
    total_pnl = sum(t["pnl"] for t in settled if t["pnl"] is not None)
    return {
        "total": len(trades),
        "pending": len([t for t in trades if t["status"] == "pending"]),
        "settled": len(settled),
        "wins": len(won),
        "win_rate": len(won) / len(settled) * 100 if settled else 0,
        "total_stake": total_stake,
        "total_pnl": total_pnl,
        "roi": total_pnl / total_stake * 100 if total_stake else 0,
    }
