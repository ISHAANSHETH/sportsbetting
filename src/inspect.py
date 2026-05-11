"""
Data inspection — show all raw data for a team/player/fighter before predicting.
Used by the 'data <name>' and 'inspect <name>' REPL commands.
"""
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.padding import Padding
from rich import box

console = Console()


def inspect_football_team(name: str) -> None:
    """Fetch and display all raw data for a football team."""
    from src.data.scrapers import fbref
    from src.data.scrapers.elo_db import get_elo, get_club_elo, get_national_elo

    console.print(f"\n[dim]Fetching data for [bold]{name}[/bold]...[/dim]")

    data = fbref.get_team_data(name)
    elo = data.get("elo") or get_elo(name)

    # Build display
    title = f"⚽  {name}"
    if data.get("is_national"):
        title += "  [dim](National Team)[/dim]"

    lines = Text()

    # ELO
    lines.append(f"  ELO Rating:       ", style="dim")
    lines.append(f"{elo:.0f}\n", style="bold white")

    # Scoring
    lines.append(f"  Avg Goals For:    ", style="dim")
    xg = data.get("avg_xg")
    goals = data.get("avg_goals", "?")
    if xg:
        lines.append(f"{goals} goals  (xG: {xg})\n", style="bold white")
    else:
        lines.append(f"{goals} goals\n", style="bold white")

    lines.append(f"  Avg Goals Against:", style="dim")
    xga = data.get("avg_xga")
    conceded = data.get("avg_conceded", "?")
    if xga:
        lines.append(f" {conceded} goals  (xGA: {xga})\n", style="bold white")
    else:
        lines.append(f" {conceded} goals\n", style="bold white")

    form = data.get("form", "?")
    form_pct = f"{float(form)*100:.0f}%" if form != "?" else "?"
    form_color = "bright_green" if form != "?" and float(form) >= 0.6 else "yellow" if form != "?" and float(form) >= 0.45 else "red"
    lines.append(f"  Form (last 10):   ", style="dim")
    lines.append(f"{form_pct}\n", style=f"bold {form_color}")

    n_matches = data.get("matches_analyzed")
    if n_matches:
        lines.append(f"  Matches analyzed: ", style="dim")
        lines.append(f"{n_matches}\n", style="white")

    sources = data.get("data_sources", [])
    if sources:
        lines.append(f"\n  Data sources:     ", style="dim")
        lines.append(", ".join(sources) + "\n", style="dim white")

    # Data quality warning
    if elo == 1700 and not xg:
        lines.append("\n  ⚠ No live data found — using ELO-derived estimates.\n", style="yellow")
        lines.append("    Prediction reliability: LOW\n", style="yellow")
    elif not xg:
        lines.append(f"\n  ℹ No xG data — using actual goals and ELO.\n", style="dim")
        lines.append(f"    Prediction reliability: MEDIUM\n", style="dim")
    else:
        lines.append(f"\n  ✓ Live xG data available.\n", style="dim green")
        lines.append(f"    Prediction reliability: HIGH\n", style="dim green")

    console.print(Panel(
        lines,
        title=f"[bold white]{title}[/bold white]",
        border_style="bright_blue",
        padding=(0, 1),
    ))


def inspect_fighter(name: str) -> None:
    """Fetch and display UFC/boxing fighter stats."""
    from src.data.scrapers import ufcstats

    console.print(f"\n[dim]Fetching stats for [bold]{name}[/bold]...[/dim]")
    stats = ufcstats.get_fighter_stats(name)

    if not stats or not stats.get("slpm"):
        console.print(f"[yellow]  No data found for '{name}'.[/yellow]")
        return

    lines = Text()
    lines.append(f"  Record:           ", style="dim")
    lines.append(f"{stats.get('wins', '?')}-{stats.get('losses', '?')}\n", style="bold white")

    total_wins = max(1, stats.get("wins", 1))
    ko_pct = stats.get("ko_wins", 0) / total_wins * 100
    sub_pct = stats.get("sub_wins", 0) / total_wins * 100
    dec_pct = stats.get("dec_wins", 0) / total_wins * 100

    lines.append(f"  Finish rates:     ", style="dim")
    lines.append(f"KO/TKO {ko_pct:.0f}%  Sub {sub_pct:.0f}%  Dec {dec_pct:.0f}%\n", style="white")
    lines.append(f"  Str/min (SLPM):   ", style="dim")
    lines.append(f"{stats.get('slpm', '?')}\n", style="white")
    lines.append(f"  Str accuracy:     ", style="dim")
    lines.append(f"{stats.get('str_acc', 0)*100:.0f}%\n", style="white")
    lines.append(f"  Str defense:      ", style="dim")
    lines.append(f"{stats.get('str_def', 0)*100:.0f}%\n", style="white")
    lines.append(f"  Takedown avg:     ", style="dim")
    lines.append(f"{stats.get('td_avg', '?')}/15min\n", style="white")
    lines.append(f"  Takedown def:     ", style="dim")
    lines.append(f"{stats.get('td_def', 0)*100:.0f}%\n", style="white")

    source = "UFCStats.com (seeded)" if stats.get("source") == "seeded" else "UFCStats.com (live)"
    lines.append(f"\n  Source: {source}\n", style="dim")

    console.print(Panel(
        lines,
        title=f"[bold white]🥊  {name}[/bold white]",
        border_style="bright_blue",
        padding=(0, 1),
    ))


def inspect_tennis_player(name: str) -> None:
    """Show tennis player serve stats and ELO."""
    from src.data.scrapers import sackmann
    from src.props.tennis import PLAYER_SERVE_SEEDS

    console.print(f"\n[dim]Fetching stats for [bold]{name}[/bold]...[/dim]")

    lines = Text()
    key = name.lower()
    serve_data = None
    for seed_name, surfaces in PLAYER_SERVE_SEEDS.items():
        if seed_name in key or key in seed_name:
            serve_data = surfaces
            break

    if serve_data:
        lines.append(f"  Serve hold (grass): ", style="dim")
        lines.append(f"{serve_data.get('grass', 0):.0%}\n", style="white")
        lines.append(f"  Serve hold (hard):  ", style="dim")
        lines.append(f"{serve_data.get('hard', 0):.0%}\n", style="white")
        lines.append(f"  Serve hold (clay):  ", style="dim")
        lines.append(f"{serve_data.get('clay', 0):.0%}\n", style="white")
    else:
        lines.append(f"  No seeded serve data — using surface defaults.\n", style="yellow")

    # Try Sackmann for recent stats
    stats = sackmann.get_player_stats(name)
    if stats:
        lines.append(f"\n  Win rate (surface adjusted): ", style="dim")
        for surface, wr in stats.items():
            if isinstance(wr, float):
                lines.append(f"{surface}: {wr:.0%}  ", style="white")
        lines.append("\n")
    lines.append(f"\n  Data source: Jeff Sackmann ATP/WTA dataset\n", style="dim")

    console.print(Panel(
        lines,
        title=f"[bold white]🎾  {name}[/bold white]",
        border_style="bright_blue",
        padding=(0, 1),
    ))


def inspect_player(name: str) -> None:
    """Show football player prop stats."""
    from src.data.scrapers.player_stats import get_player_stats

    console.print(f"\n[dim]Fetching stats for [bold]{name}[/bold]...[/dim]")
    stats = get_player_stats(name)

    lines = Text()
    lines.append(f"  Team:             ", style="dim")
    lines.append(f"{stats.get('team', 'Unknown')}\n", style="white")
    lines.append(f"  Position:         ", style="dim")
    lines.append(f"{stats.get('position', 'FW')}\n", style="white")
    lines.append(f"  xG per 90:        ", style="dim")
    lines.append(f"{stats.get('xg_per_90', '?')}\n", style="bold white")
    lines.append(f"  Goals per 90:     ", style="dim")
    lines.append(f"{stats.get('goals_per_90', '?')}\n", style="white")
    lines.append(f"  Assists per 90:   ", style="dim")
    lines.append(f"{stats.get('assists_per_90', '?')}\n", style="white")
    lines.append(f"  Avg minutes/game: ", style="dim")
    lines.append(f"{stats.get('minutes_per_game', '?')}\n", style="white")

    splits = stats.get("foot_splits", {})
    if splits:
        lines.append(f"  Shot foot splits: ", style="dim")
        lines.append(
            f"Left {splits.get('left', 0):.0%}  Right {splits.get('right', 0):.0%}  Head {splits.get('head', 0):.0%}\n",
            style="white",
        )
    dom = stats.get("dominant_foot")
    if dom:
        lines.append(f"  Dominant foot:    ", style="dim")
        lines.append(f"{dom.title()}\n", style="white")

    src = stats.get("source", "default")
    src_label = {
        "seeded": "FBRef career data (seeded)",
        "fbref": "FBRef live scrape",
        "default": "Positional average (no player-specific data)",
    }.get(src, src)
    lines.append(f"\n  Data source: {src_label}\n", style="dim")
    if src == "default":
        lines.append("  ⚠ Player not in database — prop accuracy reduced.\n", style="yellow")

    console.print(Panel(
        lines,
        title=f"[bold white]👤  {name}[/bold white]",
        border_style="bright_blue",
        padding=(0, 1),
    ))
