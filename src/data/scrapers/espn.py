"""ESPN unofficial public API — no key required."""
import requests
from src.data import cache

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"
SPORT_MAP = {
    "football": "soccer/eng.1",  # Premier League default
    "soccer": "soccer/eng.1",
    "cricket": "cricket/icc.world",
    "tennis": "tennis/atp",
    "mma": "mma/ufc",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SportsBettingPredictor/1.0)",
    "Accept": "application/json",
}


def _get(url: str, params: dict = None) -> dict:
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}


def get_team_scoreboard(sport: str = "soccer", league: str = "eng.1") -> list:
    """Fetch today's/upcoming scoreboard for a league."""
    cached = cache.get("espn_scoreboard", {"sport": sport, "league": league})
    if cached:
        return cached

    url = f"{ESPN_BASE}/{sport}/{league}/scoreboard"
    data = _get(url)
    events = []

    for event in data.get("events", []):
        competitors = event.get("competitions", [{}])[0].get("competitors", [])
        if len(competitors) >= 2:
            events.append({
                "id": event.get("id"),
                "name": event.get("name"),
                "date": event.get("date"),
                "home": competitors[0].get("team", {}).get("displayName"),
                "away": competitors[1].get("team", {}).get("displayName"),
                "home_score": competitors[0].get("score"),
                "away_score": competitors[1].get("score"),
                "status": event.get("status", {}).get("type", {}).get("name"),
            })

    cache.set("espn_scoreboard", {"sport": sport, "league": league}, events, ttl_seconds=1800)
    return events


def get_team_stats_espn(team_name: str, sport: str = "soccer", league: str = "eng.1") -> dict:
    """Fetch team statistics from ESPN."""
    cached = cache.get("espn_team", {"team": team_name, "sport": sport, "league": league})
    if cached:
        return cached

    url = f"{ESPN_BASE}/{sport}/{league}/teams"
    data = _get(url)

    team_id = None
    for team in data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
        t = team.get("team", {})
        if team_name.lower() in t.get("displayName", "").lower():
            team_id = t.get("id")
            break

    if not team_id:
        return {}

    stats_url = f"{ESPN_BASE}/{sport}/{league}/teams/{team_id}/statistics"
    stats_data = _get(stats_url)

    result = {"team": team_name, "espn_id": team_id, "stats": stats_data}
    cache.set("espn_team", {"team": team_name, "sport": sport, "league": league}, result, ttl_seconds=3600 * 6)
    return result


def search_athlete(name: str, sport: str = "tennis") -> dict:
    """Search for an athlete by name."""
    cached = cache.get("espn_athlete", {"name": name, "sport": sport})
    if cached:
        return cached

    sport_path = SPORT_MAP.get(sport, sport)
    url = f"{ESPN_BASE}/{sport_path}/athletes"
    data = _get(url, params={"limit": 50})

    for athlete in data.get("athletes", []):
        if name.lower() in athlete.get("fullName", "").lower():
            result = {
                "id": athlete.get("id"),
                "name": athlete.get("fullName"),
                "rank": athlete.get("rankings", [{}])[0].get("current") if athlete.get("rankings") else None,
            }
            cache.set("espn_athlete", {"name": name, "sport": sport}, result, ttl_seconds=3600 * 6)
            return result
    return {}
