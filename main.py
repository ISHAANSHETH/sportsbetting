#!/usr/bin/env python3
"""
EdgeFinder — Sports Betting Predictor (interactive terminal)

Run with no arguments to enter the interactive REPL:
  python main.py

Or pass a one-shot query directly:
  python main.py "Portugal vs Spain Nations League"
  python main.py "Djokovic vs Alcaraz Wimbledon"
  python main.py trades
  python main.py show sports
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.padding import Padding

console = Console()


def _banner():
    console.print()
    console.print(Panel(
        Text.assemble(
            ("  EdgeFinder", "bold bright_blue"),
            ("  ·  Sports Betting Predictor\n\n", "dim white"),
            ("  Commands:\n", "bold dim"),
            ("    <match query>  ", "white"), ("— predict (e.g. Portugal vs Spain)\n", "dim"),
            ("    trades         ", "white"), ("— view your bet history & P&L\n", "dim"),
            ("    settle <id>    ", "white"), ("— mark a trade won/lost (e.g. settle a3f9)\n", "dim"),
            ("    sports         ", "white"), ("— list all supported sports\n", "dim"),
            ("    exit           ", "white"), ("— quit\n", "dim"),
        ),
        border_style="bright_blue",
        padding=(0, 1),
    ))


def _run_prediction(query: str):
    """Run prediction and offer to log as trade. Returns the result or None."""
    from src.predictor import predict_query
    result = predict_query(query)
    if result is None:
        return None

    from src.display import terminal
    log_data = terminal.prompt_log_trade(result)
    if log_data:
        bet_outcome, bet_label, stake, odds = log_data
        from src import trades as trade_log
        trade = trade_log.log(result, bet_outcome, bet_label, stake, odds)
        console.print(
            Padding(
                Text(f"  Trade logged  [id: {trade['id']}]  — type 'settle {trade['id']}' when you know the result.",
                     style="dim green"),
                (0, 1),
            )
        )

    return result


def _show_trades():
    from src import trades as trade_log
    from src.display import terminal
    all_trades = trade_log.load()
    s = trade_log.stats(all_trades)
    terminal.render_trades(all_trades, s)


def _settle(args: str):
    from src import trades as trade_log
    from src.display import terminal
    from rich.prompt import Confirm

    parts = args.strip().split()
    if not parts:
        console.print("  Usage: settle <trade-id>", style="dim red")
        return

    trade_id = parts[0]
    trades = trade_log.load()
    match = next((t for t in trades if t["id"] == trade_id), None)

    if not match:
        console.print(f"  Trade '{trade_id}' not found.", style="red")
        return

    console.print(
        f"\n  [dim]{match['entity1']} vs {match['entity2']}  ·  Bet: [bold]{match['bet_label']}[/bold]  ·  Stake: {match['stake']}[/dim]"
    )
    won = Confirm.ask("  Did this bet win?")
    t = trade_log.settle(trade_id, won)
    pnl = t["pnl"]
    sign = "+" if pnl >= 0 else ""
    style = "bright_green" if pnl >= 0 else "red"
    console.print(
        Padding(
            Text(f"  Settled {'WIN' if won else 'LOSS'}  ·  P&L: {sign}{pnl:.1f}", style=style),
            (0, 1),
        )
    )


def _dispatch(line: str) -> bool:
    """Handle one REPL line. Returns False to exit."""
    cmd = line.strip()
    if not cmd:
        return True

    low = cmd.lower()

    if low in ("exit", "quit", "q"):
        return False

    if low in ("trades", "t", "history"):
        _show_trades()
        return True

    if low.startswith("settle ") or low.startswith("s "):
        args = cmd.split(" ", 1)[1]
        _settle(args)
        return True

    if low in ("sports", "show sports", "list sports"):
        from src.display import terminal
        terminal.render_sports_list()
        return True

    if low in ("help", "h", "?"):
        _banner()
        return True

    # Treat anything else as a match prediction query
    _run_prediction(cmd)
    return True


def _repl():
    _banner()
    while True:
        try:
            line = console.input("\n[bright_blue]>[/bright_blue] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]  Goodbye.[/dim]\n")
            break
        if not _dispatch(line):
            console.print("[dim]  Goodbye.[/dim]\n")
            break


def main():
    if len(sys.argv) >= 2:
        # One-shot mode — single command then exit
        query = " ".join(sys.argv[1:])
        low = query.strip().lower()
        if low in ("trades", "t", "history"):
            _show_trades()
        elif low.startswith("settle "):
            _settle(query.split(" ", 1)[1])
        elif low in ("sports", "show sports"):
            from src.display import terminal
            terminal.render_sports_list()
        else:
            from src.predictor import predict_query
            predict_query(query)
    else:
        _repl()


if __name__ == "__main__":
    main()
