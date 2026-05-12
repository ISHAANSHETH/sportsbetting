"""
Odds movement detector for the watchlist.
Polls Polymarket odds for watched markets and flags sudden shifts.
"""
import json
import os
from datetime import datetime, timezone
from typing import Optional

_WATCHLIST_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "watchlist.json")


def _path() -> str:
    os.makedirs(os.path.dirname(_WATCHLIST_FILE), exist_ok=True)
    return os.path.abspath(_WATCHLIST_FILE)


def load_watchlist() -> list:
    p = _path()
    if not os.path.exists(p):
        return []
    with open(p) as f:
        return json.load(f)


def save_watchlist(items: list) -> None:
    with open(_path(), "w") as f:
        json.dump(items, f, indent=2)


def add_to_watchlist(entity1: str, entity2: str, sport: str = "football") -> dict:
    """Add a market to the watchlist and snapshot current odds."""
    from src.data.market import get_market_odds
    items = load_watchlist()

    # Deduplicate
    e1, e2 = entity1.strip().lower(), entity2.strip().lower()
    for item in items:
        if item["entity1"].lower() == e1 and item["entity2"].lower() == e2:
            return item

    odds = get_market_odds(entity1, entity2, sport) or {}
    entry = {
        "entity1": entity1,
        "entity2": entity2,
        "sport": sport,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "last_odds": odds,
        "last_checked": datetime.now(timezone.utc).isoformat(),
        "moved": False,
        "alerts": [],
    }
    items.append(entry)
    save_watchlist(items)
    return entry


def remove_from_watchlist(entity1: str, entity2: str) -> bool:
    items = load_watchlist()
    before = len(items)
    e1, e2 = entity1.strip().lower(), entity2.strip().lower()
    items = [
        i for i in items
        if not (i["entity1"].lower() == e1 and i["entity2"].lower() == e2)
    ]
    if len(items) < before:
        save_watchlist(items)
        return True
    return False


def check_watchlist_movements(threshold_pp: float = 5.0) -> list:
    """
    Fetch current odds for every watched market.
    Returns list of alert dicts for markets that moved >= threshold_pp.
    Updates watchlist.json with new snapshots.
    """
    from src.data.market import get_market_odds
    items = load_watchlist()
    if not items:
        return []

    alerts = []
    now = datetime.now(timezone.utc).isoformat()

    for item in items:
        item["moved"] = False
        current = get_market_odds(item["entity1"], item["entity2"], item.get("sport", "football")) or {}
        if not current:
            item["last_checked"] = now
            continue

        last = item.get("last_odds") or {}
        item_alerts = []

        for outcome_key, new_prob in current.items():
            if outcome_key in ("source",) or new_prob is None:
                continue
            old_prob = last.get(outcome_key)
            if old_prob is None or not isinstance(old_prob, (int, float)):
                continue
            delta = (new_prob - old_prob) * 100
            if abs(delta) >= threshold_pp:
                alert = {
                    "entity1": item["entity1"],
                    "entity2": item["entity2"],
                    "sport": item.get("sport", ""),
                    "outcome": outcome_key,
                    "old_prob": round(old_prob * 100, 1),
                    "new_prob": round(new_prob * 100, 1),
                    "delta_pp": round(delta, 1),
                    "detected_at": now,
                }
                alerts.append(alert)
                item_alerts.append(alert)
                item["moved"] = True

        item["last_odds"] = current
        item["last_checked"] = now
        if item_alerts:
            item.setdefault("alerts", [])
            item["alerts"] = (item["alerts"] + item_alerts)[-20:]  # keep last 20

    save_watchlist(items)
    return alerts
