"""Cross-book arbitrage scanner: groups odds snapshots by game/market/line,
finds the best price per outcome across ALL books, and flags true
arbitrage opportunities (best-price implied probabilities summing to
under 100%).

Scope note on spread/total lines: a real, riskless arbitrage requires the
two legs to be at the SAME market line (e.g. both quoting the total at
47.5) — pairing Home -3 at one book with Away +4 at another can create a
"middle" (a shot at winning both bets) but is not a guaranteed, riskless
arbitrage, since both legs can still lose if the game lands between the
two numbers. This scanner therefore only compares prices within identical
lines and does not attempt to price middles.

Freshness: every leg carries the `captured_at` timestamp of the pull that
produced it. `max_pull_gap_seconds` is the time between the OLDEST and
NEWEST leg making up a flagged opportunity — if that exceeds
`staleness_threshold_seconds`, the opportunity is marked stale, since one
side's price may have already moved by the time both legs could be placed.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd

from arbitrage.arb_math import ArbLeg, best_leg, evaluate, apply_stake_split, guaranteed_profit
from data_pipeline.schema import OddsSnapshot

DEFAULT_STALENESS_THRESHOLD_SECONDS = 60.0

MARKETS = ("moneyline", "spread", "total")

# Odds APIs (including The Odds API, this repo's reference source) do not
# expose per-book bet limits. Rather than fabricate a number, every scan
# result carries this fixed caveat instead of a fake "max stake" column.
LIQUIDITY_CAVEAT = (
    "Book bet-size limits are not available from this data source. A book "
    "that is mispricing a line may cap how much of the split stake is "
    "actually fillable at the displayed price — verify each book's max "
    "stake before staking anything."
)


@dataclass
class ArbOpportunity:
    game_id: str
    sport: str
    market: str
    home_team: str
    away_team: str
    line: float | None          # shared spread/total point for both legs; None for moneyline
    legs: list[ArbLeg]
    sum_implied_prob: float
    arb_margin: float
    guaranteed_profit: float
    total_stake: float
    max_pull_gap_seconds: float
    is_stale: bool


def _line_key(market: str, home_point: float | None) -> float | None:
    if market == "moneyline":
        return None
    return round(home_point, 1) if home_point is not None else None


def _group_by_line(snapshots: list[OddsSnapshot], market: str) -> dict[float | None, list[OddsSnapshot]]:
    groups: dict[float | None, list[OddsSnapshot]] = {}
    for s in snapshots:
        if s.market != market or s.home_price is None or s.away_price is None:
            continue
        groups.setdefault(_line_key(market, s.home_point), []).append(s)
    return groups


def _max_gap_seconds(legs: list[ArbLeg]) -> float:
    times = [dt.datetime.fromisoformat(leg.captured_at) for leg in legs]
    return (max(times) - min(times)).total_seconds()


def find_arbs_for_game_market(
    snapshots: list[OddsSnapshot],
    sport: str,
    game_id: str,
    home_team: str,
    away_team: str,
    market: str,
    total_stake: float,
    staleness_threshold_seconds: float = DEFAULT_STALENESS_THRESHOLD_SECONDS,
) -> list[ArbOpportunity]:
    """Scans every distinct line quoted for `market` in this game and
    returns one ArbOpportunity per line where the best cross-book prices
    sum to under 100% implied probability. An empty list is the common,
    expected result — most scans find nothing, and that is not an error."""
    opportunities: list[ArbOpportunity] = []
    for line, group in _group_by_line(snapshots, market).items():
        home_quotes = [(s.book, s.home_price, s.captured_at) for s in group]
        away_quotes = [(s.book, s.away_price, s.captured_at) for s in group]
        home_leg = best_leg("home", home_quotes)
        away_leg = best_leg("away", away_quotes)
        if home_leg is None or away_leg is None:
            continue

        result = evaluate([home_leg, away_leg])
        if not result.is_arbitrage:
            continue

        apply_stake_split(result, total_stake)
        profit = guaranteed_profit(result, total_stake)
        gap = _max_gap_seconds(result.legs)
        opportunities.append(
            ArbOpportunity(
                game_id=game_id, sport=sport, market=market, home_team=home_team, away_team=away_team,
                line=line, legs=result.legs, sum_implied_prob=result.sum_implied_prob,
                arb_margin=result.arb_margin, guaranteed_profit=profit, total_stake=total_stake,
                max_pull_gap_seconds=gap, is_stale=gap > staleness_threshold_seconds,
            )
        )
    return opportunities


def scan_game(
    snapshots: list[OddsSnapshot],
    sport: str,
    game_id: str,
    home_team: str,
    away_team: str,
    total_stake: float,
    staleness_threshold_seconds: float = DEFAULT_STALENESS_THRESHOLD_SECONDS,
    markets: tuple[str, ...] = MARKETS,
) -> list[ArbOpportunity]:
    out: list[ArbOpportunity] = []
    for market in markets:
        out.extend(
            find_arbs_for_game_market(
                snapshots, sport, game_id, home_team, away_team, market, total_stake, staleness_threshold_seconds
            )
        )
    return out


def _side_label(market: str, side: str) -> str:
    # ingest_odds.parse_odds_api_event stores Over in the 'home' slot and
    # Under in the 'away' slot for totals — see its docstring/comments.
    if market == "total":
        return "over" if side == "home" else "under"
    return side


OUTPUT_COLUMNS = [
    "sport", "game", "market", "line",
    "side_a", "side_a_book", "side_a_odds", "side_a_stake",
    "side_b", "side_b_book", "side_b_odds", "side_b_stake",
    "arb_margin_pct", "guaranteed_profit", "total_stake",
    "captured_at_earliest", "captured_at_latest", "pull_gap_seconds", "stale",
]


def opportunities_to_frame(opportunities: list[ArbOpportunity]) -> pd.DataFrame:
    """One row per flagged opportunity, sorted by arb_margin_pct descending.
    Returns a correctly-columned but empty frame when `opportunities` is
    empty — a clean scan with nothing found is a valid, expected result."""
    if not opportunities:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    rows = []
    for o in opportunities:
        a, b = o.legs[0], o.legs[1]
        times = [dt.datetime.fromisoformat(leg.captured_at) for leg in o.legs]
        rows.append(
            {
                "sport": o.sport,
                "game": f"{o.away_team} @ {o.home_team}",
                "market": o.market,
                "line": o.line,
                "side_a": _side_label(o.market, a.side),
                "side_a_book": a.book,
                "side_a_odds": a.american_odds,
                "side_a_stake": round(a.stake, 2),
                "side_b": _side_label(o.market, b.side),
                "side_b_book": b.book,
                "side_b_odds": b.american_odds,
                "side_b_stake": round(b.stake, 2),
                "arb_margin_pct": o.arb_margin,
                "guaranteed_profit": round(o.guaranteed_profit, 2),
                "total_stake": o.total_stake,
                "captured_at_earliest": min(times).isoformat(),
                "captured_at_latest": max(times).isoformat(),
                "pull_gap_seconds": o.max_pull_gap_seconds,
                "stale": o.is_stale,
            }
        )
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS).sort_values("arb_margin_pct", ascending=False).reset_index(drop=True)
