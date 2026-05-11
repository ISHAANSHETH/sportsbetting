"""
Live fixtures and upcoming matches from ESPN unofficial API.
Covers football, tennis, UFC, cricket, boxing — no key needed.
"""
import requests
from datetime import datetime, timedelta
from src.data import cache

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SportsBettingPredictor/1.0)",
    "Accept": "application/json",
}

# All major football leagues available on ESPN
FOOTBALL_LEAGUES = [
    ("soccer", "eng.1",    "Premier League 🏴󠁧󠁢󠁥󠁮󠁧󠁿"),
    ("soccer", "esp.1",    "La Liga 🇪🇸"),
    ("soccer", "ger.1",    "Bundesliga 🇩🇪"),
    ("soccer", "ita.1",    "Serie A 🇮🇹"),
    ("soccer", "fra.1",    "Ligue 1 🇫🇷"),
    ("soccer", "uefa.champions", "Champions League 🏆"),
    ("soccer", "uefa.europa",    "Europa League 🏆"),
    ("soccer", "uefa.nations",   "Nations League 🌍"),
    ("soccer", "fifa.world",     "World Cup 🌍"),
    ("soccer", "fifa.worldq.uefa", "WC Qualifiers Europe 🌍"),
    ("soccer", "usa.1",    "MLS 🇺🇸"),
    ("soccer", "ned.1",    "Eredivisie 🇳🇱"),
    ("soccer", "por.1",    "Primeira Liga 🇵🇹"),
    ("soccer", "tur.1",    "Süper Lig 🇹🇷"),
    ("soccer", "mex.1",    "Liga MX 🇲🇽"),
    ("soccer", "bra.1",    "Brasileirão 🇧🇷"),
    ("soccer", "arg.1",    "Liga Profesional 🇦🇷"),
    ("soccer", "sco.1",    "Scottish Prem 🏴󠁧󠁢󠁳󠁣󠁴󠁿"),
    ("soccer", "col.1",    "Liga BetPlay 🇨🇴"),
    ("soccer", "jpn.1",    "J-League 🇯🇵"),
    ("soccer", "sau.1",    "Saudi Pro League 🇸🇦"),
]

OTHER_SPORTS = [
    ("tennis", "atp",       "ATP Tennis 🎾"),
    ("tennis", "wta",       "WTA Tennis 🎾"),
    ("mma",    "ufc",       "UFC 🥊"),
    ("boxing", "boxing",    "Boxing 🥊"),
    ("cricket","icc.world", "Cricket 🏏"),
]


def _get(url: str, params: dict = None) -> dict:
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}


def _parse_events(data: dict, league_label: str) -> list:
    events = []
    for event in data.get("events", []):
        comps = event.get("competitions", [{}])
        comp = comps[0] if comps else {}
        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            continue

        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

        status_obj = event.get("status", {})
        status = status_obj.get("type", {}).get("description", "Scheduled")
        clock = status_obj.get("displayClock", "")
        period = status_obj.get("period", 0)

        events.append({
            "league": league_label,
            "name": event.get("name", ""),
            "date": event.get("date", ""),
            "home": home.get("team", {}).get("displayName", ""),
            "away": away.get("team", {}).get("displayName", ""),
            "home_score": home.get("score", ""),
            "away_score": away.get("score", ""),
            "status": status,
            "clock": clock,
            "period": period,
            "venue": comp.get("venue", {}).get("fullName", ""),
        })
    return events


def get_todays_fixtures(sports: list = None, days_ahead: int = 1) -> list:
    """
    Fetch today's + upcoming fixtures across all major sports.
    Returns list of event dicts sorted by date.
    """
    cache_key = {"days": days_ahead, "sports": str(sports)}
    cached = cache.get("fixtures_today", cache_key)
    if cached:
        return cached

    all_events = []
    today = datetime.utcnow()

    leagues = FOOTBALL_LEAGUES if sports is None else [
        l for l in FOOTBALL_LEAGUES if "soccer" in l[0]
    ]
    if sports is None:
        leagues += OTHER_SPORTS

    for sport, league_id, label in leagues:
        for day_offset in range(days_ahead + 1):
            date_str = (today + timedelta(days=day_offset)).strftime("%Y%m%d")
            url = f"{ESPN_BASE}/{sport}/{league_id}/scoreboard"
            data = _get(url, params={"dates": date_str, "limit": 30})
            events = _parse_events(data, label)
            all_events.extend(events)

    # Sort by date
    all_events.sort(key=lambda e: e.get("date", ""))
    # Deduplicate
    seen = set()
    unique = []
    for e in all_events:
        key = (e["home"], e["away"], e["date"][:10])
        if key not in seen:
            seen.add(key)
            unique.append(e)

    cache.set("fixtures_today", cache_key, unique, ttl_seconds=900)  # 15 min cache
    return unique


def search_fixture(team1: str, team2: str, days_ahead: int = 7) -> dict | None:
    """Find a specific upcoming fixture between two teams."""
    all_fixtures = get_todays_fixtures(days_ahead=days_ahead)
    t1 = team1.lower()
    t2 = team2.lower()

    for f in all_fixtures:
        h = f["home"].lower()
        a = f["away"].lower()
        if (t1 in h or any(w in h for w in t1.split())
                or t1 in a or any(w in a for w in t1.split())):
            if (t2 in h or any(w in h for w in t2.split())
                    or t2 in a or any(w in a for w in t2.split())):
                return f
    return None


def get_live_scores() -> list:
    """Return only in-progress matches right now."""
    all_events = get_todays_fixtures(days_ahead=0)
    return [e for e in all_events if e["status"] in ("In Progress", "Halftime", "Final")]
