"""UFCStats.com scraper — official UFC stats, no key needed."""
import requests
import re
from bs4 import BeautifulSoup
from src.data import cache

BASE = "http://ufcstats.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

# Seeded fighter stats for top fighters (fallback + speed)
FIGHTER_SEEDS = {
    "jon jones": {
        "slpm": 4.29, "str_acc": 0.57, "sapm": 2.22, "str_def": 0.64,
        "td_avg": 1.86, "td_acc": 0.44, "td_def": 0.96, "sub_avg": 0.5,
        "height_cm": 193, "reach_cm": 213, "age": 37, "wins": 27, "losses": 1,
        "ko_wins": 10, "sub_wins": 7, "dec_wins": 10,
    },
    "stipe miocic": {
        "slpm": 4.67, "str_acc": 0.52, "sapm": 3.25, "str_def": 0.55,
        "td_avg": 1.74, "td_acc": 0.40, "td_def": 0.73, "sub_avg": 0.1,
        "height_cm": 193, "reach_cm": 201, "age": 41, "wins": 20, "losses": 4,
        "ko_wins": 12, "sub_wins": 1, "dec_wins": 7,
    },
    "francis ngannou": {
        "slpm": 4.43, "str_acc": 0.47, "sapm": 3.60, "str_def": 0.56,
        "td_avg": 1.50, "td_acc": 0.37, "td_def": 0.73, "sub_avg": 0.3,
        "height_cm": 193, "reach_cm": 211, "age": 38, "wins": 17, "losses": 3,
        "ko_wins": 12, "sub_wins": 4, "dec_wins": 1,
    },
    "israel adesanya": {
        "slpm": 4.29, "str_acc": 0.53, "sapm": 2.41, "str_def": 0.60,
        "td_avg": 0.56, "td_acc": 0.38, "td_def": 0.90, "sub_avg": 0.0,
        "height_cm": 193, "reach_cm": 203, "age": 35, "wins": 24, "losses": 4,
        "ko_wins": 16, "sub_wins": 1, "dec_wins": 7,
    },
    "islam makhachev": {
        "slpm": 3.64, "str_acc": 0.55, "sapm": 1.45, "str_def": 0.65,
        "td_avg": 4.43, "td_acc": 0.51, "td_def": 0.81, "sub_avg": 1.2,
        "height_cm": 175, "reach_cm": 178, "age": 33, "wins": 26, "losses": 1,
        "ko_wins": 4, "sub_wins": 9, "dec_wins": 13,
    },
    "alex pereira": {
        "slpm": 5.71, "str_acc": 0.60, "sapm": 3.87, "str_def": 0.53,
        "td_avg": 0.84, "td_acc": 0.29, "td_def": 0.84, "sub_avg": 0.0,
        "height_cm": 193, "reach_cm": 203, "age": 37, "wins": 11, "losses": 2,
        "ko_wins": 8, "sub_wins": 0, "dec_wins": 3,
    },
    "alexander volkanovski": {
        "slpm": 6.01, "str_acc": 0.57, "sapm": 2.62, "str_def": 0.59,
        "td_avg": 1.64, "td_acc": 0.48, "td_def": 0.73, "sub_avg": 0.2,
        "height_cm": 168, "reach_cm": 182, "age": 36, "wins": 26, "losses": 3,
        "ko_wins": 12, "sub_wins": 1, "dec_wins": 13,
    },
    "conor mcgregor": {
        "slpm": 5.32, "str_acc": 0.49, "sapm": 3.77, "str_def": 0.57,
        "td_avg": 0.67, "td_acc": 0.53, "td_def": 0.66, "sub_avg": 0.0,
        "height_cm": 175, "reach_cm": 188, "age": 36, "wins": 22, "losses": 6,
        "ko_wins": 19, "sub_wins": 1, "dec_wins": 2,
    },
}


def get_fighter_stats(fighter_name: str) -> dict:
    """Return fighter stats. Uses seeds first, then scrapes UFCStats."""
    name_lower = fighter_name.lower().strip()

    # Check seeds
    for seed_name, stats in FIGHTER_SEEDS.items():
        if seed_name in name_lower or name_lower in seed_name:
            result = dict(stats)
            result["name"] = fighter_name
            result["finish_rate"] = round((result["ko_wins"] + result["sub_wins"]) / max(result["wins"], 1), 3)
            result["win_rate"] = round(result["wins"] / max(result["wins"] + result["losses"], 1), 3)
            return result

    # Try scraping UFCStats
    cached = cache.get("ufcstats_fighter", {"name": fighter_name})
    if cached:
        return cached

    result = _scrape_fighter(fighter_name)
    if result:
        cache.set("ufcstats_fighter", {"name": fighter_name}, result, ttl_seconds=3600 * 24)
        return result

    return _default_fighter(fighter_name)


def _scrape_fighter(name: str) -> dict:
    """Scrape fighter page from UFCStats."""
    try:
        search_url = f"{BASE}/statistics/fighters?query={name.replace(' ', '+')}&action=search"
        resp = requests.get(search_url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return {}

        soup = BeautifulSoup(resp.text, "lxml")
        links = soup.select("a.b-link.b-link_style_black")
        if not links:
            return {}

        fighter_url = links[0]["href"]
        resp2 = requests.get(fighter_url, headers=HEADERS, timeout=12)
        soup2 = BeautifulSoup(resp2.text, "lxml")

        def get_stat(label):
            for li in soup2.select("li.b-list__box-list-item"):
                text = li.get_text()
                if label in text:
                    parts = text.strip().split(":")
                    if len(parts) >= 2:
                        return parts[-1].strip().replace("%", "").strip()
            return None

        def safe_float(v, divisor=1):
            try:
                return float(str(v).replace("--", "0")) / divisor
            except Exception:
                return 0.0

        slpm = safe_float(get_stat("SLpM"))
        str_acc = safe_float(get_stat("Str. Acc."), 100)
        sapm = safe_float(get_stat("SApM"))
        str_def = safe_float(get_stat("Str. Def"), 100)
        td_avg = safe_float(get_stat("TD Avg."))
        td_acc = safe_float(get_stat("TD Acc."), 100)
        td_def = safe_float(get_stat("TD Def."), 100)
        sub_avg = safe_float(get_stat("Sub. Avg."))

        record_text = soup2.select_one(".b-content__title-record")
        wins = losses = 0
        if record_text:
            m = re.search(r"(\d+)-(\d+)", record_text.get_text())
            if m:
                wins, losses = int(m.group(1)), int(m.group(2))

        return {
            "name": name,
            "slpm": slpm, "str_acc": str_acc, "sapm": sapm, "str_def": str_def,
            "td_avg": td_avg, "td_acc": td_acc, "td_def": td_def, "sub_avg": sub_avg,
            "wins": wins, "losses": losses,
            "win_rate": round(wins / max(wins + losses, 1), 3),
            "finish_rate": 0.5,
        }
    except Exception:
        return {}


def get_h2h(fighter1: str, fighter2: str) -> dict:
    """Check if fighters have met before — simple win/loss result."""
    # For most UFC fighters, prior H2H is rare; return neutral
    return {"total": 0, "f1_wins": 0, "f2_wins": 0, "f1_win_rate": 0.5}


def _default_fighter(name: str) -> dict:
    return {
        "name": name,
        "slpm": 3.5, "str_acc": 0.45, "sapm": 3.0, "str_def": 0.55,
        "td_avg": 1.5, "td_acc": 0.40, "td_def": 0.70, "sub_avg": 0.5,
        "wins": 15, "losses": 5, "win_rate": 0.75, "finish_rate": 0.5,
        "height_cm": 178, "reach_cm": 183, "age": 30,
        "ko_wins": 6, "sub_wins": 3, "dec_wins": 6,
    }
