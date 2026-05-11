"""Rich terminal display for prediction results."""
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich import box
from rich.rule import Rule
from rich.padding import Padding

console = Console()

OUTCOME_LABELS = {
    "home_win": "Home Win",
    "draw": "Draw",
    "away_win": "Away Win",
    "p1_win": "Win",
    "p2_win": "Win",
    "f1_win": "Win",
    "f2_win": "Win",
}

EDGE_COLORS = {
    "STRONG": "bold green",
    "MODERATE": "yellow",
    "WEAK": "dim white",
    "NEGATIVE": "red",
}


def _prob_bar(prob: float, width: int = 20) -> str:
    if prob is None:
        return "─" * width
    filled = int(round(prob * width))
    empty = width - filled
    return "█" * filled + "░" * empty


def _outcome_label(key: str, entity1: str, entity2: str) -> str:
    if key in ("home_win", "p1_win", "f1_win"):
        return entity1
    if key in ("away_win", "p2_win", "f2_win"):
        return entity2
    if key == "draw":
        return "Draw"
    return key.replace("_", " ").title()


def render(result) -> None:
    """Render a PredictionResult to the terminal."""
    console.print()

    # Header
    sport_emoji = {
        "Football": "⚽", "Tennis": "🎾", "UFC/MMA": "🥊",
        "Boxing": "🥊", "Cricket": "🏏", "Darts": "🎯",
        "Badminton": "🏸", "Table Tennis": "🏓",
    }.get(result.sport, "🏆")

    title = f"{sport_emoji}  {result.entity1}  vs  {result.entity2}"
    subtitle = f"{result.competition}  •  {result.date}" if result.competition else result.date
    if result.venue and result.venue not in ("Unknown", ""):
        subtitle += f"  •  {result.venue}"

    console.print(Panel(
        Text(subtitle, justify="center", style="dim"),
        title=f"[bold white]{title}[/bold white]",
        border_style="bright_blue",
        padding=(0, 2),
    ))

    # Probability table
    prob_table = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style="bold dim",
        padding=(0, 1),
        expand=True,
    )
    prob_table.add_column("Outcome", style="white", min_width=16)
    prob_table.add_column("Probability", min_width=28)
    prob_table.add_column("Model %", justify="right", min_width=8)
    prob_table.add_column("Market %", justify="right", min_width=8)
    prob_table.add_column("Edge", justify="right", min_width=9)

    market_probs = result.market_probs or {}
    edges = result.edges or {}

    for key, prob in result.probabilities.items():
        if prob is None:
            continue

        label = _outcome_label(key, result.entity1, result.entity2)
        bar = _prob_bar(prob)
        model_pct = f"{prob * 100:.1f}%"

        mkt_p = market_probs.get(key)
        mkt_str = f"{mkt_p * 100:.1f}%" if mkt_p is not None else "N/A"

        edge_info = edges.get(key, {})
        edge_val = edge_info.get("edge_pct", None)
        if edge_val is not None:
            sign = "+" if edge_val > 0 else ""
            edge_str = f"{sign}{edge_val:.1f}%"
            edge_color = EDGE_COLORS.get(edge_info.get("rating", "WEAK"), "white")
        else:
            edge_str = "—"
            edge_color = "dim"

        # Highlight best bet row
        is_best = key == result.best_bet
        row_style = "bold" if is_best else ""

        prob_table.add_row(
            Text(("★ " if is_best else "  ") + label, style=f"{row_style} {'bright_yellow' if is_best else 'white'}"),
            Text(bar, style="bright_blue" if prob > 0.5 else "white"),
            Text(model_pct, style=f"{row_style} bright_white"),
            Text(mkt_str, style="dim"),
            Text(edge_str, style=f"{row_style} {edge_color}"),
        )

    console.print(Padding(prob_table, (0, 1)))

    # Key factors
    if result.key_factors or result.news_flags:
        factors_text = Text()
        for f in result.key_factors[:4]:
            factors_text.append(f"  • {f}\n", style="dim white")
        for f in result.news_flags[:3]:
            factors_text.append(f"  ⚠ {f}\n", style="yellow")

        console.print(Panel(
            factors_text,
            title="[dim]Key Factors[/dim]",
            border_style="dim",
            padding=(0, 1),
        ))

    # Recommendation box
    if result.best_bet and result.best_edge_pct > 0:
        best_label = _outcome_label(result.best_bet, result.entity1, result.entity2)
        edge_color = "bright_green" if result.best_edge_pct >= 5 else "yellow"
        edge_rating = "STRONG VALUE" if result.best_edge_pct >= 5 else "MODERATE VALUE" if result.best_edge_pct >= 2 else "WEAK VALUE"

        rec_text = Text()
        rec_text.append(f"  Best Bet: {best_label}\n", style="bold bright_white")
        rec_text.append(f"  Edge over market: ", style="dim")
        rec_text.append(f"+{result.best_edge_pct:.1f}%  [{edge_rating}]\n", style=f"bold {edge_color}")
        rec_text.append(f"  Kelly Stake: ", style="dim")
        rec_text.append(f"{result.kelly_stake_pct:.1f}% of bankroll\n", style="bold white")
        rec_text.append(f"  Model Confidence: ", style="dim")
        rec_text.append(f"{result.confidence:.0f}/100\n", style="bold white")

        console.print(Panel(
            rec_text,
            title="[bold bright_green]★  RECOMMENDED BET[/bold bright_green]",
            border_style=edge_color,
            padding=(0, 1),
        ))
    else:
        console.print(Panel(
            Text("  No clear edge detected vs market odds — pass on this one.", style="dim"),
            title="[dim]Recommendation[/dim]",
            border_style="dim",
        ))

    # Model breakdown
    breakdown_parts = []
    for model_name, model_probs in (result.model_breakdown or {}).items():
        if model_probs:
            key = next((k for k in ["home_win", "p1_win", "f1_win"] if k in model_probs), None)
            if key:
                breakdown_parts.append(f"{model_name}: {model_probs[key]*100:.1f}%")

    if breakdown_parts:
        console.print(
            Padding(
                Text("  Models: " + "  |  ".join(breakdown_parts), style="dim"),
                (0, 1)
            )
        )

    # Data sources
    sources_str = " · ".join(result.data_sources) if result.data_sources else "Seeded data"
    console.print(Padding(Text(f"  Data: {sources_str}", style="dim"), (0, 1)))
    console.print()


def render_sports_list():
    """Show all supported sports and their data sources."""
    console.print()
    table = Table(title="Supported Sports", box=box.ROUNDED, border_style="bright_blue")
    table.add_column("Sport", style="bold white")
    table.add_column("Accuracy Target", style="bright_green")
    table.add_column("Data Source", style="dim")
    table.add_column("Why Predictable", style="dim white")

    sports = [
        ("⚽ Football/Soccer", "~63%", "FBRef, Understat, ESPN", "Dixon-Coles xG model"),
        ("🎾 Tennis", "~68%", "Jeff Sackmann ATP/WTA CSVs", "Surface ELO, serve stats"),
        ("🥊 UFC/MMA", "~63%", "UFCStats.com", "Strike/grapple differentials"),
        ("🥊 Boxing", "~62%", "BoxRec, Tapology", "ELO + style matchups"),
        ("🏏 Cricket", "~66%", "CricSheet ball-by-ball", "Batting/bowling averages"),
        ("🎯 Darts", "~67%", "PDC rankings", "Most consistent sport"),
        ("🏸 Badminton", "~64%", "BWF world rankings", "1v1 ELO very predictive"),
        ("🏓 Table Tennis", "~64%", "ITTF rankings", "Consistent, high data"),
    ]

    for row in sports:
        table.add_row(*row)

    console.print(table)
    console.print(Padding(
        Text("Usage: python main.py \"Portugal vs Spain Nations League\"", style="dim"),
        (1, 2)
    ))
    console.print()


def render_error(message: str):
    console.print(Panel(
        Text(f"  {message}", style="red"),
        title="[red]Error[/red]",
        border_style="red",
    ))
    console.print(Padding(
        Text('Try: python main.py "Portugal vs Spain"  or  python main.py "show sports"', style="dim"),
        (0, 2)
    ))
