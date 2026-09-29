"""Round-4 probe: ESPN league injury feed structure (NFL/NBA), team roster shape."""
import json

import requests

for lg, sp in (("nfl", "football"), ("nba", "basketball")):
    r = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/{sp}/{lg}/injuries", timeout=30)
    print(lg, r.status_code, len(r.content))
    if r.ok:
        d = r.json()
        print(" top keys:", list(d.keys()))
        inj = d.get("injuries", [])
        print(" n team blocks:", len(inj))
        if inj:
            b = inj[0]
            print(" block keys:", list(b.keys()))
            print(" block sample:", json.dumps({k: v for k, v in b.items() if k != "injuries"})[:600])
            if b.get("injuries"):
                print(" injury[0]:", json.dumps(b["injuries"][0])[:2000])
r = requests.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/3/roster", timeout=30)
d = r.json()
print("roster keys", list(d.keys()), "athletes[0] keys", list(d["athletes"][0].keys()) if d.get("athletes") else None)
print(json.dumps(d["athletes"][0])[:800])
