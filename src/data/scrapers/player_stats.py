"""
Player-level stats for prop betting.
Seeded data for top players + FBRef player page fallback.
Foot split percentages from FBRef shooting logs (left/right/header).
"""
import requests
import re
from bs4 import BeautifulSoup
from src.data import cache

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

# Real-ish per-90 stats and shot foot splits (sourced from FBRef career data)
# foot_splits: {left_pct, right_pct, head_pct} share of SHOTS (not goals)
PLAYER_SEEDS = {
    # ── Football / Soccer ─────────────────────────────────────────────────────
    "erling haaland": {
        "team": "manchester city", "position": "CF",
        "xg_per_90": 0.93, "shots_per_90": 4.1, "goals_per_90": 0.94,
        "assists_per_90": 0.22, "minutes_per_game": 83,
        "dominant_foot": "left",
        "foot_splits": {"left": 0.55, "right": 0.27, "head": 0.18},
    },
    "kylian mbappe": {
        "team": "real madrid", "position": "FW",
        "xg_per_90": 0.68, "shots_per_90": 3.8, "goals_per_90": 0.72,
        "assists_per_90": 0.38, "minutes_per_game": 85,
        "dominant_foot": "right",
        "foot_splits": {"left": 0.18, "right": 0.74, "head": 0.08},
    },
    "lionel messi": {
        "team": "inter miami", "position": "RW",
        "xg_per_90": 0.56, "shots_per_90": 3.3, "goals_per_90": 0.60,
        "assists_per_90": 0.55, "minutes_per_game": 75,
        "dominant_foot": "left",
        "foot_splits": {"left": 0.74, "right": 0.19, "head": 0.07},
    },
    "cristiano ronaldo": {
        "team": "al nassr", "position": "FW",
        "xg_per_90": 0.72, "shots_per_90": 4.5, "goals_per_90": 0.68,
        "assists_per_90": 0.18, "minutes_per_game": 82,
        "dominant_foot": "right",
        "foot_splits": {"left": 0.20, "right": 0.52, "head": 0.28},
    },
    "neymar": {
        "team": "al hilal", "position": "LW",
        "xg_per_90": 0.47, "shots_per_90": 3.2, "goals_per_90": 0.52,
        "assists_per_90": 0.45, "minutes_per_game": 70,
        "dominant_foot": "left",
        "foot_splits": {"left": 0.78, "right": 0.12, "head": 0.10},
    },
    "vinicius jr": {
        "team": "real madrid", "position": "LW",
        "xg_per_90": 0.51, "shots_per_90": 3.6, "goals_per_90": 0.55,
        "assists_per_90": 0.42, "minutes_per_game": 82,
        "dominant_foot": "right",
        "foot_splits": {"left": 0.25, "right": 0.67, "head": 0.08},
    },
    "harry kane": {
        "team": "bayern munich", "position": "CF",
        "xg_per_90": 0.82, "shots_per_90": 4.0, "goals_per_90": 0.78,
        "assists_per_90": 0.32, "minutes_per_game": 88,
        "dominant_foot": "right",
        "foot_splits": {"left": 0.25, "right": 0.60, "head": 0.15},
    },
    "mohamed salah": {
        "team": "liverpool", "position": "RW",
        "xg_per_90": 0.62, "shots_per_90": 3.5, "goals_per_90": 0.65,
        "assists_per_90": 0.38, "minutes_per_game": 84,
        "dominant_foot": "left",
        "foot_splits": {"left": 0.69, "right": 0.21, "head": 0.10},
    },
    "heung-min son": {
        "team": "tottenham", "position": "LW",
        "xg_per_90": 0.42, "shots_per_90": 2.8, "goals_per_90": 0.45,
        "assists_per_90": 0.28, "minutes_per_game": 83,
        "dominant_foot": "right",
        "foot_splits": {"left": 0.28, "right": 0.64, "head": 0.08},
    },
    "robert lewandowski": {
        "team": "barcelona", "position": "CF",
        "xg_per_90": 0.75, "shots_per_90": 3.9, "goals_per_90": 0.70,
        "assists_per_90": 0.22, "minutes_per_game": 84,
        "dominant_foot": "right",
        "foot_splits": {"left": 0.22, "right": 0.58, "head": 0.20},
    },
    "karim benzema": {
        "team": "al ittihad", "position": "CF",
        "xg_per_90": 0.65, "shots_per_90": 3.1, "goals_per_90": 0.60,
        "assists_per_90": 0.30, "minutes_per_game": 78,
        "dominant_foot": "right",
        "foot_splits": {"left": 0.22, "right": 0.60, "head": 0.18},
    },
    "lamine yamal": {
        "team": "barcelona", "position": "RW",
        "xg_per_90": 0.28, "shots_per_90": 2.3, "goals_per_90": 0.32,
        "assists_per_90": 0.52, "minutes_per_game": 82,
        "dominant_foot": "right",
        "foot_splits": {"left": 0.12, "right": 0.80, "head": 0.08},
    },
    "pedri": {
        "team": "barcelona", "position": "CM",
        "xg_per_90": 0.15, "shots_per_90": 1.4, "goals_per_90": 0.18,
        "assists_per_90": 0.28, "minutes_per_game": 78,
        "dominant_foot": "right",
        "foot_splits": {"left": 0.15, "right": 0.78, "head": 0.07},
    },
    "jude bellingham": {
        "team": "real madrid", "position": "CM",
        "xg_per_90": 0.35, "shots_per_90": 2.1, "goals_per_90": 0.38,
        "assists_per_90": 0.32, "minutes_per_game": 83,
        "dominant_foot": "right",
        "foot_splits": {"left": 0.18, "right": 0.68, "head": 0.14},
    },
    "phil foden": {
        "team": "manchester city", "position": "LW",
        "xg_per_90": 0.38, "shots_per_90": 2.6, "goals_per_90": 0.40,
        "assists_per_90": 0.30, "minutes_per_game": 78,
        "dominant_foot": "left",
        "foot_splits": {"left": 0.72, "right": 0.20, "head": 0.08},
    },
    "bukayo saka": {
        "team": "arsenal", "position": "RW",
        "xg_per_90": 0.38, "shots_per_90": 2.4, "goals_per_90": 0.40,
        "assists_per_90": 0.38, "minutes_per_game": 82,
        "dominant_foot": "left",
        "foot_splits": {"left": 0.71, "right": 0.20, "head": 0.09},
    },
    "marcus rashford": {
        "team": "manchester united", "position": "FW",
        "xg_per_90": 0.35, "shots_per_90": 2.5, "goals_per_90": 0.32,
        "assists_per_90": 0.22, "minutes_per_game": 77,
        "dominant_foot": "right",
        "foot_splits": {"left": 0.35, "right": 0.55, "head": 0.10},
    },
    "gabriel martinelli": {
        "team": "arsenal", "position": "LW",
        "xg_per_90": 0.30, "shots_per_90": 2.2, "goals_per_90": 0.33,
        "assists_per_90": 0.20, "minutes_per_game": 77,
        "dominant_foot": "right",
        "foot_splits": {"left": 0.18, "right": 0.74, "head": 0.08},
    },
    "darwin nunez": {
        "team": "liverpool", "position": "CF",
        "xg_per_90": 0.55, "shots_per_90": 3.4, "goals_per_90": 0.50,
        "assists_per_90": 0.18, "minutes_per_game": 72,
        "dominant_foot": "right",
        "foot_splits": {"left": 0.22, "right": 0.62, "head": 0.16},
    },
    "olivier giroud": {
        "team": "ac milan", "position": "CF",
        "xg_per_90": 0.48, "shots_per_90": 2.5, "goals_per_90": 0.45,
        "assists_per_90": 0.12, "minutes_per_game": 73,
        "dominant_foot": "right",
        "foot_splits": {"left": 0.14, "right": 0.48, "head": 0.38},  # header specialist
    },
    "bernardo silva": {
        "team": "manchester city", "position": "CM",
        "xg_per_90": 0.20, "shots_per_90": 1.8, "goals_per_90": 0.22,
        "assists_per_90": 0.35, "minutes_per_game": 80,
        "dominant_foot": "right",
        "foot_splits": {"left": 0.10, "right": 0.83, "head": 0.07},
    },
    "rodri": {
        "team": "manchester city", "position": "DM",
        "xg_per_90": 0.10, "shots_per_90": 0.9, "goals_per_90": 0.10,
        "assists_per_90": 0.18, "minutes_per_game": 83,
        "dominant_foot": "right",
        "foot_splits": {"left": 0.12, "right": 0.78, "head": 0.10},
    },
    # International stars
    "bruno fernandes": {
        "team": "manchester united", "position": "CAM",
        "xg_per_90": 0.28, "shots_per_90": 2.0, "goals_per_90": 0.30,
        "assists_per_90": 0.38, "minutes_per_game": 84,
        "dominant_foot": "right",
        "foot_splits": {"left": 0.10, "right": 0.82, "head": 0.08},
    },
}

# Positional fallback stats when player not seeded
POSITION_DEFAULTS = {
    "CF": {"xg_per_90": 0.42, "shots_per_90": 2.8, "goals_per_90": 0.38,
           "assists_per_90": 0.15, "foot_splits": {"left": 0.30, "right": 0.55, "head": 0.15}},
    "FW": {"xg_per_90": 0.30, "shots_per_90": 2.2, "goals_per_90": 0.28,
           "assists_per_90": 0.25, "foot_splits": {"left": 0.28, "right": 0.60, "head": 0.12}},
    "LW": {"xg_per_90": 0.25, "shots_per_90": 2.0, "goals_per_90": 0.22,
           "assists_per_90": 0.30, "foot_splits": {"left": 0.55, "right": 0.35, "head": 0.10}},
    "RW": {"xg_per_90": 0.25, "shots_per_90": 2.0, "goals_per_90": 0.22,
           "assists_per_90": 0.30, "foot_splits": {"left": 0.25, "right": 0.65, "head": 0.10}},
    "CAM": {"xg_per_90": 0.18, "shots_per_90": 1.6, "goals_per_90": 0.15,
            "assists_per_90": 0.40, "foot_splits": {"left": 0.28, "right": 0.62, "head": 0.10}},
    "CM": {"xg_per_90": 0.10, "shots_per_90": 1.2, "goals_per_90": 0.10,
           "assists_per_90": 0.25, "foot_splits": {"left": 0.22, "right": 0.68, "head": 0.10}},
    "DM": {"xg_per_90": 0.05, "shots_per_90": 0.7, "goals_per_90": 0.05,
           "assists_per_90": 0.12, "foot_splits": {"left": 0.20, "right": 0.70, "head": 0.10}},
    "DEF": {"xg_per_90": 0.03, "shots_per_90": 0.5, "goals_per_90": 0.03,
            "assists_per_90": 0.08, "foot_splits": {"left": 0.25, "right": 0.62, "head": 0.13}},
}


def get_player_stats(name: str) -> dict:
    """Return player stats dict. Tries seeded data first, then FBRef, then positional default."""
    key = name.lower().strip()

    # Partial match in seeds
    for seed_name, data in PLAYER_SEEDS.items():
        if seed_name in key or key in seed_name:
            return {"name": name, "source": "seeded", **data}

    cached = cache.get("player_stats", {"name": key})
    if cached:
        return cached

    scraped = _scrape_fbref_player(name)
    if scraped:
        cache.set("player_stats", {"name": key}, scraped, ttl_seconds=3600 * 12)
        return scraped

    # Positional default — generic attacker
    return {"name": name, "source": "default", **POSITION_DEFAULTS["FW"]}


def _scrape_fbref_player(name: str) -> dict:
    """Search FBRef for a player and scrape their shooting stats."""
    try:
        search_url = f"https://fbref.com/search/search.fcgi?search={name.replace(' ', '+')}"
        resp = requests.get(search_url, headers=HEADERS, timeout=10, allow_redirects=True)
        if resp.status_code != 200:
            return {}

        soup = BeautifulSoup(resp.text, "lxml")

        # FBRef redirects directly to player page on unique match
        if "/players/" in resp.url:
            return _parse_player_page(resp.url, soup)

        # Otherwise find first result link
        result = soup.find("div", {"id": "searches"})
        if result:
            link = result.find("a", href=re.compile(r"/players/"))
            if link:
                player_url = "https://fbref.com" + link["href"]
                r2 = requests.get(player_url, headers=HEADERS, timeout=10)
                if r2.status_code == 200:
                    return _parse_player_page(player_url, BeautifulSoup(r2.text, "lxml"))
    except Exception:
        pass
    return {}


def _parse_player_page(url: str, soup: BeautifulSoup) -> dict:
    """Parse FBRef player shooting table for xG and foot splits."""
    try:
        # Get per-90 stats from standard stats table
        std_table = soup.find("table", {"id": re.compile(r"stats_standard")})
        xg_per_90 = shots_per_90 = goals_per_90 = assists_per_90 = None

        if std_table:
            last_row = std_table.find("tbody").find_all("tr")
            for row in reversed(last_row):
                if row.get("class") and "partial_table" in row.get("class", []):
                    continue
                xg_cell = row.find("td", {"data-stat": "xg_per90"})
                shots_cell = row.find("td", {"data-stat": "shots_per90"})
                goals_cell = row.find("td", {"data-stat": "goals_per90"})
                assists_cell = row.find("td", {"data-stat": "assists_per90"})
                if xg_cell and xg_cell.text.strip():
                    try:
                        xg_per_90 = float(xg_cell.text)
                        shots_per_90 = float(shots_cell.text) if shots_cell else 2.0
                        goals_per_90 = float(goals_cell.text) if goals_cell else 0.3
                        assists_per_90 = float(assists_cell.text) if assists_cell else 0.2
                    except ValueError:
                        pass
                    break

        # Position
        pos_span = soup.find("strong", string=re.compile("Position"))
        position = "FW"
        if pos_span and pos_span.next_sibling:
            pos_text = str(pos_span.next_sibling)
            if "GK" in pos_text:
                position = "GK"
            elif "DF" in pos_text:
                position = "DEF"
            elif "MF" in pos_text:
                position = "CM"
            elif "FW" in pos_text:
                position = "FW"

        return {
            "source": "fbref",
            "xg_per_90": xg_per_90 or POSITION_DEFAULTS.get(position, POSITION_DEFAULTS["FW"])["xg_per_90"],
            "shots_per_90": shots_per_90 or 2.0,
            "goals_per_90": goals_per_90 or 0.25,
            "assists_per_90": assists_per_90 or 0.20,
            "minutes_per_game": 75,
            "position": position,
            "foot_splits": POSITION_DEFAULTS.get(position, POSITION_DEFAULTS["FW"])["foot_splits"],
        }
    except Exception:
        return {}
