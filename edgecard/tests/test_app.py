"""The Streamlit viewer: locked without the password, renders a card with a
bet in it (and a NO BET tier) without exceptions once unlocked."""
from __future__ import annotations

import json

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

CARD = {
    "generated_at": "2026-10-04T14:00:00+00:00", "generated_at_et": "Sun Oct 04 10:00 AM ET", "mode": "full",
    "paper_mode": True, "bankroll": 10000, "disclaimer": "Probabilities, not guarantees.", "warnings": [],
    "leagues": {"NFL": {"league": "NFL", "n_games": 1, "model": {"note": "market-only"}, "tiers": {
        "SAFE": {"id": "abc", "tier": "SAFE", "status": "WAIT", "recheck_at": "2026-10-04T15:30:00+00:00",
                 "description": "BUF ML", "book": "outlier", "price": -160, "min_acceptable_price": -175,
                 "model_prob": 0.703, "novig_market_prob": 0.703, "price_implied_prob": 0.615, "edge": 0.088,
                 "ev_per_100": 14.3, "stake": 200.0, "reasons": ["Best price -160 at outlier"], "notes": [],
                 "flags": [{"flag_type": "official_status", "severity": 2, "player": "J. Allen", "text": "questionable",
                            "source": "ESPN", "url": None, "timestamp": "2026-10-03T20:00:00Z"}],
                 "legs": [{"label": "BUF ML", "game": "NYJ @ BUF", "kickoff": "2026-10-04T17:00:00Z", "book": "outlier",
                           "price": -160, "p_final": 0.703, "novig_implied": 0.703, "p_model": None}]},
        "MODERATE": {"bet": None, "message": "NO BET", "reason": "nothing clears 2%"},
        "LONG SHOT": {"bet": None, "message": "NO LONG SHOT TODAY", "reason": "no +EV combo"}},
        "shadow_props": {"status": "SHADOW ONLY", "rows": []}}},
    "freshness": {"nfl.espn.odds": {"ok": True, "rows": 42, "note": "", "checked_at": "2026-10-04T14:00:00+00:00"}},
}


def test_app_locked_then_renders(tmp_path, monkeypatch):
    (tmp_path / "cards").mkdir()
    (tmp_path / "cards" / "latest.json").write_text(json.dumps(CARD))
    monkeypatch.setenv("EDGECARD_DATA_DIR", str(tmp_path))
    at = AppTest.from_file("../app/streamlit_app.py", default_timeout=30)
    at.secrets["APP_PASSWORD"] = "correct horse"
    at.run()
    assert not any("BUF ML" in m.value for m in at.markdown)  # locked
    at.text_input[0].input("nope").run()
    assert any("Wrong password" in e.value for e in at.error)
    at.text_input[0].input("correct horse").run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "BUF ML" in text and "NO LONG SHOT TODAY" in text
    assert any("WAIT" in w.value for w in at.warning)
