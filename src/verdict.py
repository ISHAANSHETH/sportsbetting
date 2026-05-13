"""
LLM-powered betting verdict.

Turns a PredictionResult into a structured YES/NO/MARGINAL recommendation
with a short reason and risk factors. Uses the Anthropic SDK with adaptive
thinking and prompt caching on the (stable) system prompt.

Requires ANTHROPIC_API_KEY in the environment.
"""
from __future__ import annotations

import json
import os
from typing import Literal, Optional

from pydantic import BaseModel, Field


_MODEL = "claude-opus-4-7"

_SYSTEM = """You are a disciplined sports-betting analyst evaluating whether a bet has positive expected value worth taking.

You will be given a JSON payload describing a single proposed bet: the matchup, the model's outcome probabilities, the devigged market-implied probabilities, the computed edge per outcome, the model's "best bet" pick, the Kelly stake percentage, the model's confidence, key factors driving the pick, any news flags (injuries, suspensions, late news), and the data sources that fed the model.

Your job: decide BET, SKIP, or MARGINAL, and explain in 1-2 sentences why.

Decision criteria, in priority order:

1. **Edge sign and magnitude.** A non-positive edge → SKIP. Edge >= 5% on the best outcome is a strong signal. 2-5% is moderate. 0-2% is weak — usually MARGINAL unless every other criterion is excellent.

2. **Kelly stake.** Kelly <= 0 → SKIP. Kelly < 1% → MARGINAL. Kelly >= 2% with a real edge → BET-worthy.

3. **Confidence and data sources.** If `confidence` < 55 or `data_sources` is sparse (one source, or only "Model"), be cautious — downgrade BET → MARGINAL.

4. **News flags.** Any injury / suspension / red-flag item in `news_flags` should usually drop the call by one level (BET → MARGINAL, MARGINAL → SKIP) unless the model clearly accounts for it via `key_factors`.

5. **Market vs model sanity check.** If model and market probabilities disagree by more than ~15 percentage points on the best bet, treat the edge as suspicious — likely the market knows something the model doesn't. Drop to MARGINAL or SKIP.

6. **Missing market data.** If `market_probs` is null or empty, you cannot verify edge — call MARGINAL at best, regardless of model confidence.

Examples:

- Edge +6.5% on best_bet, Kelly 2.1%, confidence 72, no news flags, three data sources → BET, "Strong edge with reliable inputs and clean news picture."

- Edge +1.2% on best_bet, Kelly 0.4%, confidence 60, one news flag (key player doubtful) → SKIP, "Marginal edge wiped out by injury uncertainty not reflected in the model."

- Edge +3.5%, Kelly 1.5%, but model 64% vs market 50% (14pp gap) → MARGINAL, "Gap with market is large enough to suggest hidden information; size down or skip."

- No market_probs → MARGINAL, "No market available to verify edge — model pick is not actionable as a value bet."

Output a single JSON object matching the provided schema. Keep `reason` to 1-2 sentences. Include 1-3 `risk_factors` only when they materially change the call; omit otherwise. `confidence` reflects how confident you are in your decision (not the model's confidence)."""


class Verdict(BaseModel):
    decision: Literal["BET", "SKIP", "MARGINAL"]
    reason: str = Field(..., description="1-2 sentence justification for the decision")
    confidence: Literal["low", "medium", "high"] = Field(
        ..., description="How confident you are in this verdict"
    )
    risk_factors: list[str] = Field(
        default_factory=list,
        description="0-3 specific risks the bettor should weigh; omit when none materially apply",
    )


def is_configured() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _payload_from_result(result) -> dict:
    """Build a serializable summary of the PredictionResult for the LLM."""
    return {
        "matchup": f"{result.entity1} vs {result.entity2}",
        "sport": result.sport,
        "competition": result.competition or None,
        "date": result.date,
        "venue": result.venue,
        "is_neutral": result.is_neutral,
        "bet_type": result.bet_type,
        "prop_description": result.prop_description or None,
        "probabilities": result.probabilities,
        "market_probs": result.market_probs,
        "edges": result.edges,
        "best_bet": result.best_bet,
        "best_edge_pct": result.best_edge_pct,
        "kelly_stake_pct": result.kelly_stake_pct,
        "confidence": result.confidence,
        "key_factors": result.key_factors,
        "news_flags": result.news_flags,
        "data_sources": result.data_sources,
        "model_breakdown": result.model_breakdown,
    }


def get_verdict(result) -> Optional[Verdict]:
    """
    Call Claude to produce a verdict on a PredictionResult.

    Returns a Verdict, or None if the SDK isn't installed / configured / errored.
    """
    if not is_configured():
        return None

    try:
        import anthropic
    except ImportError:
        return None

    client = anthropic.Anthropic()
    payload_json = json.dumps(_payload_from_result(result), indent=2, default=str)

    try:
        response = client.messages.parse(
            model=_MODEL,
            max_tokens=2048,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"Evaluate this bet:\n\n```json\n{payload_json}\n```",
                }
            ],
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            output_format=Verdict,
        )
    except anthropic.AuthenticationError:
        return None
    except anthropic.APIError:
        return None
    except Exception:
        return None

    return response.parsed_output


def render_verdict(verdict: Verdict) -> None:
    """Print a rich panel summarizing the verdict below the existing prediction."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich import box

    console = Console()

    style_by_decision = {
        "BET": ("bright_green", "✓ BET"),
        "MARGINAL": ("yellow", "~ MARGINAL"),
        "SKIP": ("red", "✗ SKIP"),
    }
    color, label = style_by_decision.get(verdict.decision, ("dim white", verdict.decision))

    conf_color = {"high": "bright_green", "medium": "yellow", "low": "red"}.get(verdict.confidence, "dim")

    body = Text()
    body.append(f"  {label}", style=f"bold {color}")
    body.append(f"  ·  confidence: ", style="dim")
    body.append(f"{verdict.confidence}", style=conf_color)
    body.append("\n\n  ")
    body.append(verdict.reason, style="white")

    if verdict.risk_factors:
        body.append("\n\n  Risks:\n", style="dim")
        for rf in verdict.risk_factors[:3]:
            body.append(f"    · {rf}\n", style="dim yellow")

    console.print(
        Panel(
            body,
            title="[bold]Claude's Take[/bold]",
            border_style=color,
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )


def ask_about(query: str) -> None:
    """
    Run the existing prediction pipeline, then add an LLM verdict below.

    Used by `main.py` as the `ask` REPL command.
    """
    from rich.console import Console

    console = Console()

    if not is_configured():
        console.print(
            "[red]  ANTHROPIC_API_KEY not set.[/red]  "
            "[dim]Add it to .env to enable the `ask` command.[/dim]"
        )
        return

    from src.predictor import predict_query

    result = predict_query(query)
    if result is None:
        return

    console.print("[dim]  Asking Claude...[/dim]")
    verdict = get_verdict(result)
    if verdict is None:
        console.print(
            "[red]  Verdict failed.[/red]  "
            "[dim]Check ANTHROPIC_API_KEY and `pip install anthropic`.[/dim]"
        )
        return

    render_verdict(verdict)
