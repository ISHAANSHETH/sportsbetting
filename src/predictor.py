"""Main orchestrator — routes parsed query to the correct sport handler."""
from typing import Optional
from src import parser as query_parser
from src.sports.football import FootballPredictor
from src.sports.tennis import TennisPredictor
from src.sports.ufc import UFCPredictor
from src.sports.boxing import BoxingPredictor
from src.sports.cricket import CricketPredictor
from src.sports.darts import DartsPredictor, BadmintonPredictor
from src.display import terminal
from src.sports.base import PredictionResult


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


def run(query: str) -> None:
    """Parse query and execute prediction pipeline."""
    predict_query(query)


def predict_query(query: str) -> Optional[PredictionResult]:
    """Parse query, run prediction, render result. Returns PredictionResult or None."""
    parsed = query_parser.parse(query)

    if "command" in parsed:
        if parsed["command"] == "show_sports":
            terminal.render_sports_list()
        elif parsed["command"] == "help":
            _show_help()
        return None

    if "error" in parsed:
        terminal.render_error(parsed["error"])
        return None

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
        terminal.render_error(f"Sport '{sport}' is not yet supported.")
        return None

    terminal.console.print(f"\n[dim]Analyzing {entity1} vs {entity2} ({sport.title()})...[/dim]")

    try:
        result = handler.predict(entity1, entity2, date, context)
        terminal.render(result)
        return result
    except Exception as e:
        terminal.render_error(f"Prediction failed: {e}")
        return None


def _show_help():
    from rich.console import Console
    from rich.padding import Padding
    from rich.text import Text
    c = Console()
    c.print("\n[bold]Sports Betting Predictor[/bold]")
    c.print(Padding(Text(
        "Usage: python main.py \"<team1> vs <team2> [competition] [date]\"\n\n"
        "Examples:\n"
        "  python main.py \"Portugal vs Spain Nations League\"\n"
        "  python main.py \"Djokovic vs Alcaraz Wimbledon tomorrow\"\n"
        "  python main.py \"Jon Jones vs Stipe Miocic UFC\"\n"
        "  python main.py \"India vs Australia T20 World Cup\"\n"
        "  python main.py \"show sports\"\n\n"
        "No API keys required. All data from public sources.",
        style="dim"
    ), (0, 2)))
