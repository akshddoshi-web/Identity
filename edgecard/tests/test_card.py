"""End-to-end card tests on fabricated odds (no network).

  - identical prices at every book => no edge => NO BET in every tier
  - one book clearly off-market on a favourite's moneyline => that bet is
    the SAFE pick, at that book, with a capped quarter-Kelly stake
  - the LONG SHOT tier says NO LONG SHOT TODAY rather than forcing a bet
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

import edgecard.card as card_mod
from edgecard import store
from models.nfl_props import TeamProjection


def _event(gk: str, home: str, away: str, hours: int) -> dict:
    ko = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours)).isoformat()
    return dict(league="NFL", espn_id=gk, game_key=gk, commence_time=ko, home_team=home, away_team=away,
                home_espn_id="1", away_espn_id="2", status="pre", neutral=False, home_score=None, away_score=None,
                venue=None, week=4, captured_at=dt.datetime.now(dt.timezone.utc).isoformat())


def _rows(gk, ev, book, ml_home, ml_away, spread_home=-6.5, sp_prices=(-110, -110), total=44.5, tot_prices=(-110, -110)):
    base = dict(league="NFL", game_key=gk, espn_id=gk, commence_time=ev["commence_time"], home_team=ev["home_team"],
                away_team=ev["away_team"], source="test", book=book, line_type="current",
                captured_at=dt.datetime.now(dt.timezone.utc).isoformat(), tag="live")
    return [dict(base, market="moneyline", side="home", point=None, price=ml_home),
            dict(base, market="moneyline", side="away", point=None, price=ml_away),
            dict(base, market="spread", side="home", point=spread_home, price=sp_prices[0]),
            dict(base, market="spread", side="away", point=-spread_home, price=sp_prices[1]),
            dict(base, market="total", side="over", point=total, price=tot_prices[0]),
            dict(base, market="total", side="under", point=total, price=tot_prices[1])]


@pytest.fixture()
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setenv("EDGECARD_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(card_mod, "_model_means", lambda *a, **k: {})
    monkeypatch.setattr(card_mod, "_key_players", lambda *a, **k: [])
    monkeypatch.setattr(card_mod, "_nfl_team_projections",
                        lambda ev: (TeamProjection(ev["home_team"], 62, 0.58, 0.4), TeamProjection(ev["away_team"], 62, 0.58, 0.4)))
    import news.verify as nv

    monkeypatch.setattr(nv, "fetch_injury_designations", lambda league: [])
    monkeypatch.setattr(nv, "scan_news", lambda *a, **k: [])
    return tmp_path


def _write(events, rows):
    day = dt.date.today().isoformat()
    store.append_parquet(pd.DataFrame(events), "events", "nfl", f"{day}.parquet")
    store.append_parquet(pd.DataFrame(rows), "odds", "nfl", f"{day}.parquet")


def test_no_edge_means_no_bet(tmp_store):
    ev = _event("NFL_A", "KC", "LV", 30)
    rows = []
    for b in ("dk", "fd", "mgm"):
        rows += _rows("NFL_A", ev, b, -300, 245)
    _write([ev], rows)
    out = card_mod.build_league_card("NFL", 10000.0, "full", card_mod.load_config())
    for tier in ("SAFE", "MODERATE", "LONG SHOT"):
        assert out["tiers"][tier].get("id") is None
    assert out["tiers"]["LONG SHOT"]["message"] == "NO LONG SHOT TODAY"
    assert out["tiers"]["SAFE"]["message"] == "NO BET"


def test_off_market_price_is_the_safe_pick(tmp_store):
    ev = _event("NFL_B", "BUF", "NYJ", 30)
    rows = []
    for b in ("dk", "fd", "mgm", "czr"):
        rows += _rows("NFL_B", ev, b, -250, 205)
    rows += _rows("NFL_B", ev, "outlier", -160, 135)  # home ML far better than consensus
    _write([ev], rows)
    out = card_mod.build_league_card("NFL", 10000.0, "full", card_mod.load_config())
    safe = out["tiers"]["SAFE"]
    assert safe.get("id") is not None, safe
    assert safe["book"] == "outlier" and safe["legs"][0]["market"] == "moneyline" and safe["legs"][0]["side"] == "home"
    assert safe["edge"] >= 0.02 and safe["ev_per_100"] > 0
    assert 0 < safe["stake"] <= 0.02 * 10000.0 + 1e-6
    assert safe["model_prob"] >= 0.55
    # fair prob should be close to the consensus no-vig of -250/+205
    from edgecard.pricing import novig_two_way

    fair = novig_two_way(-250, 205)[0]
    assert abs(safe["legs"][0]["p_final"] - fair) < 0.02
    assert out["tiers"]["LONG SHOT"].get("id") is None


def test_no_parlays_on_exchanges(tmp_store):
    """Two correlated same-game legs at an exchange must never become a parlay."""
    ev = _event("NFL_C", "NYG", "ARI", 30)
    rows = []
    for b in ("dk", "fd", "mgm"):
        rows += _rows("NFL_C", ev, b, 110, -130, spread_home=1.5, sp_prices=(-110, -110), total=44.5)
    rows += _rows("NFL_C", ev, "kalshi", 115, -120, spread_home=1.5, sp_prices=(-104, -100), total=44.5, tot_prices=(104, -108))
    _write([ev], rows)
    out = card_mod.build_league_card("NFL", 10000.0, "full", card_mod.load_config())
    for tier in ("SAFE", "MODERATE", "LONG SHOT"):
        v = out["tiers"][tier]
        if v.get("id"):
            assert not (len(v["legs"]) > 1 and v["book"] == "kalshi")
