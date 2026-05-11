"""Natural language parser for sports match queries."""
import re
import json
from datetime import datetime, timedelta
from pathlib import Path

TEAMS_FILE = Path(__file__).parent.parent / "data" / "mappings" / "teams.json"
PLAYERS_FILE = Path(__file__).parent.parent / "data" / "mappings" / "players.json"

DATE_KEYWORDS = {
    "today": 0, "tonight": 0, "now": 0,
    "tomorrow": 1, "tmrw": 1,
    "monday": None, "tuesday": None, "wednesday": None,
    "thursday": None, "friday": None, "saturday": None, "sunday": None,
}
WEEKDAY_MAP = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
               "friday": 4, "saturday": 5, "sunday": 6}

SPORT_INDICATORS = {
    "table tennis": ["table tennis", "ittf", "ping pong", "fan zhendong", "ma long"],
    "darts": ["darts", "pdc", "bdo", "premier league darts", "world darts",
              "van gerwen", "mvg", "littler", "humphries"],
    "badminton": ["badminton", "bwf", "all england", "thomas cup", "axelsen",
                  "carolina marin", "shi yuqi"],
    "cricket": ["cricket", "test match", " odi ", " t20 ", "t20i", "ipl", "ashes",
                "bcci", "batting", "bowling", "wicket", "t20 world cup", "cricket world cup"],
    "tennis": ["atp", "wta", "wimbledon", "us open", "french open", "australian open",
               "roland garros", "grand slam", "masters 1000", "tennis",
               "djokovic", "alcaraz", "sinner", "swiatek", "sabalenka", "nadal"],
    "ufc": ["ufc", " mma ", "fight night", "bellator", "one fc", "ufc ppv",
            "makhachev", "adesanya", "volkanovski", "mcgregor"],
    "boxing": ["boxing", "wbc", "wba", "ibf", "wbo", "heavyweight boxing",
               "boxing title", "world boxing", "fury", "usyk", "canelo", "joshua"],
    "football": ["football", "soccer", "fc ", " fc", " united", "city fc",
                 "premier league", "la liga", "bundesliga", "serie a", "ligue 1",
                 "champions league", "world cup", "euros", "euro ", "copa america",
                 "nations league", "afcon", "friendly"],
}

NEUTRAL_KEYWORDS = ["neutral", "at wembley", "at munich", "at doha", "world cup",
                    "euro final", "at stadium", "hosted by"]
COMPETITION_PATTERNS = [
    r"(world cup|euro \d{4}|euros?|copa america|afcon|nations league|"
    r"champions league|premier league|la liga|bundesliga|serie a|ligue 1|"
    r"wimbledon|us open|french open|australian open|roland garros|"
    r"grand slam|masters|ufc \d+|ipl|ashes|t20 world cup|cricket world cup|"
    r"pdc world|uk open|premier league darts)",
]


def _load_all_known_names() -> dict:
    """Load all known team/player names for entity resolution."""
    names = {}
    try:
        teams = json.loads(TEAMS_FILE.read_text())
        for sport, team_map in teams.items():
            for alias, info in team_map.items():
                names[alias.lower()] = {"sport": sport, "canonical": info.get("name", alias)}
    except Exception:
        pass

    try:
        players = json.loads(PLAYERS_FILE.read_text())
        for sport, player_map in players.items():
            for alias, info in player_map.items():
                names[alias.lower()] = {"sport": sport, "canonical": info.get("name", alias)}
    except Exception:
        pass

    return names


def _parse_date(text: str) -> str:
    """Extract date from text. Returns ISO date string."""
    text_lower = text.lower()
    today = datetime.now().date()

    for kw, delta in DATE_KEYWORDS.items():
        if kw in text_lower:
            if delta is not None:
                return str(today + timedelta(days=delta))
            # Weekday
            if kw in WEEKDAY_MAP:
                target_wd = WEEKDAY_MAP[kw]
                days_ahead = (target_wd - today.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                return str(today + timedelta(days=days_ahead))

    # Try to match date patterns: "May 15", "15 May", "2026-05-15"
    date_patterns = [
        r"(\d{4}-\d{2}-\d{2})",
        r"(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{4}?)",
        r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+\d{4})?)",
    ]
    for pattern in date_patterns:
        m = re.search(pattern, text_lower, re.IGNORECASE)
        if m:
            try:
                from dateutil import parser as dateparser
                dt = dateparser.parse(m.group(1), default=datetime(today.year, today.month, today.day))
                return str(dt.date())
            except Exception:
                pass

    return str(today + timedelta(days=1))  # default: tomorrow


def _extract_entities(text: str, known_names: dict) -> tuple:
    """Extract two competing entities (teams or players) from text."""
    text_lower = text.lower()

    # Split on "vs", "versus", "v ", " - "
    vs_patterns = [r"\bvs\.?\b", r"\bversus\b", r"\bv\b(?=\s)", r" - "]
    entities = None
    for pat in vs_patterns:
        parts = re.split(pat, text_lower, flags=re.IGNORECASE)
        if len(parts) == 2:
            entities = [p.strip() for p in parts]
            break

    if not entities or len(entities) < 2:
        return None, None

    e1_raw, e2_raw = entities

    def resolve(raw: str) -> str:
        # Remove date/competition noise
        clean = re.sub(
            r"\b(tomorrow|today|tonight|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
            r"next week|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
            r"\d{4}|\d{1,2}(?:st|nd|rd|th)?)\b",
            "", raw, flags=re.IGNORECASE
        ).strip()
        clean = re.sub(r"\s+", " ", clean).strip()

        # Check known names
        for alias, info in known_names.items():
            if alias in clean:
                return info["canonical"]

        # Return cleaned title-case
        return clean.title() if clean else raw.title()

    return resolve(e1_raw), resolve(e2_raw)


def _detect_sport(text: str, e1: str = "", e2: str = "") -> str:
    """Detect sport from text and entity names."""
    full_text = (text + " " + e1 + " " + e2).lower()

    # Check entity names against known sport mappings — only trust for
    # unambiguous sport-specific entities (not "football" which shares names)
    known = _load_all_known_names()
    for entity in [e1.lower(), e2.lower()]:
        for alias, info in known.items():
            if (alias == entity or alias in entity.split() or entity == alias):
                sport = info.get("sport", "")
                if sport in ["tennis", "ufc", "boxing"]:
                    return sport

    # Keyword-based detection — ordered most specific to least specific
    detection_order = ["table tennis", "darts", "badminton", "cricket", "tennis", "ufc", "boxing", "football"]
    for sport_name in detection_order:
        keywords = SPORT_INDICATORS.get(sport_name, [])
        if any(kw in full_text for kw in keywords):
            return sport_name

    # If both entities are known football teams, return football
    for entity in [e1.lower(), e2.lower()]:
        for alias, info in known.items():
            if alias == entity and info.get("sport") == "football":
                return "football"

    return "football"  # default


def _extract_competition(text: str) -> str:
    """Extract competition/tournament name from text."""
    for pattern in COMPETITION_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).title()
    return ""


def parse(query: str) -> dict:
    """
    Parse a natural language sports query.
    Returns: {entity1, entity2, date, sport, competition, is_neutral, raw_query}
    """
    known = _load_all_known_names()
    entity1, entity2 = _extract_entities(query, known)

    if not entity1 or not entity2:
        # Try to handle "show sports" or other commands
        if "show sports" in query.lower() or "list sports" in query.lower():
            return {"command": "show_sports"}
        if "help" in query.lower():
            return {"command": "help"}
        return {"error": f"Could not identify two competitors in: '{query}'"}

    date = _parse_date(query)
    sport = _detect_sport(query, entity1, entity2)
    competition = _extract_competition(query)
    is_neutral = any(kw in query.lower() for kw in NEUTRAL_KEYWORDS)

    return {
        "entity1": entity1,
        "entity2": entity2,
        "date": date,
        "sport": sport,
        "competition": competition,
        "is_neutral": is_neutral,
        "venue": "",
        "raw_query": query,
    }
