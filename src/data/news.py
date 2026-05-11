"""Google News RSS fetcher — no API key required."""
import re
import xml.etree.ElementTree as ET
import requests
from datetime import datetime, timezone
from typing import Optional
from src.data import cache

try:
    import feedparser
    _HAS_FEEDPARSER = True
except ImportError:
    _HAS_FEEDPARSER = False

NEGATIVE_KEYWORDS = [
    "injury", "injured", "doubtful", "doubt", "suspended", "suspension",
    "crisis", "crisis", "fired", "sacked", "illness", "ill", "ruled out",
    "out of", "withdraw", "withdrawn", "unfit", "concern", "concern",
    "not training", "missed training", "hamstring", "knee", "ankle",
    "muscle", "torn", "fracture", "surgery"
]
POSITIVE_KEYWORDS = [
    "returns", "return", "fit", "recovered", "back in", "cleared",
    "available", "training", "sharp form", "confidence", "motivation"
]

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SportsBettingPredictor/1.0)"}


def _fetch_rss(url: str) -> list:
    """Fetch RSS feed and return list of (title, published) tuples."""
    if _HAS_FEEDPARSER:
        try:
            feed = feedparser.parse(url)
            return [(e.get("title", ""), e.get("published", "")) for e in feed.entries]
        except Exception:
            pass

    # Fallback: parse RSS XML manually
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.text)
        items = []
        for item in root.iter("item"):
            title_el = item.find("title")
            pub_el = item.find("pubDate")
            title = title_el.text if title_el is not None else ""
            pub = pub_el.text if pub_el is not None else ""
            items.append((title, pub))
        return items
    except Exception:
        return []


def _score_headline(text: str) -> float:
    text_lower = text.lower()
    score = 0.0
    for kw in NEGATIVE_KEYWORDS:
        if kw in text_lower:
            score -= 0.1
    for kw in POSITIVE_KEYWORDS:
        if kw in text_lower:
            score += 0.05
    return max(-0.5, min(0.3, score))


def get_sentiment(entity: str, days: int = 2) -> dict:
    """Fetch news for an entity and return sentiment score + flagged headlines."""
    cached = cache.get("news", {"entity": entity})
    if cached:
        return cached

    query = entity.replace(" ", "+") + "+sport"
    url = GOOGLE_NEWS_RSS.format(query=query)

    entries = _fetch_rss(url)
    now = datetime.now(timezone.utc)
    score = 0.0
    flags = []
    headlines = []

    for title, pub_str in entries[:20]:
        s = _score_headline(title)
        score += s
        headlines.append(title)
        if s < -0.05:
            flags.append(title[:80])

    result = {
        "score": round(max(-0.5, min(0.3, score)), 3),
        "flags": flags[:5],
        "headlines": headlines[:10],
    }
    cache.set("news", {"entity": entity}, result, ttl_seconds=3600)
    return result
