"""Round-6 probe: Action Network dated scoreboard + team abbreviations."""
import json

import requests

for q in ["?period=game&date=20261004", "?period=game&bookIds=15,30,68,69,71,75,79&date=20261004", "?period=game&week=4",
          "?period=game&bookIds=15,30,68,69,71,75,79,123,247,280,972,1005,1006&date=20261004"]:
    r = requests.get("https://api.actionnetwork.com/web/v1/scoreboard/nfl" + q, timeout=20)
    d = r.json() if r.ok else {}
    gs = d.get("games", [])
    print(r.status_code, q, "games:", len(gs), r.text[:200] if not r.ok else "")
    if gs:
        g = gs[0]
        print("  start", g.get("start_time"), "teams", [(t.get("id"), t.get("abbr"), t.get("full_name")) for t in g.get("teams", [])],
              "home_id", g.get("home_team_id"), "n odds", len(g.get("odds", [])), "books", sorted({o.get("book_id") for o in g.get("odds", [])}))
