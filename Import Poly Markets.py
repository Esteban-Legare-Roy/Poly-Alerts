"""
real_time_polymarket_sports.py
--------------------------------
Display live Polymarket odds for every open MLB or NFL game.
Requires: pip install requests
"""

import requests, time, datetime as dt

BASE = "https://gamma-api.polymarket.com"
REFRESH_SECONDS = 60
SPORT_KEYWORDS = ("mlb", "nfl")        # extend to nba, epl, etc. if desired


def live_sports_events() -> list[dict]:
    """Return all active MLB & NFL events (games)."""
    r = requests.get(f"{BASE}/events", params={"active": "true"}, timeout=10)
    r.raise_for_status()
    events = r.json()
    print(f"DEBUG: Found {len(events)} total events")
    
    # Debug: show all sports events
    sports_events = [e for e in events if "sports" in (e.get("category") or "").lower()]
    print(f"DEBUG: Found {len(sports_events)} sports events")
    
    # For now, return all sports events instead of just MLB/NFL
    return sports_events


def markets_for(event_id: str) -> list[dict]:
    """Return markets attached to an event."""
    r = requests.get(f"{BASE}/markets", params={"eventId": event_id}, timeout=10)
    r.raise_for_status()
    return r.json()


def print_board(events: list[dict]):
    """Pretty-print prices for every event/market/outcome."""
    timestamp = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n==== {timestamp}  — Polymarket live odds ====\n")

    for ev in events:
        print(f"🏟️  {ev['title']}  (eventId {ev['id']})")
        for m in markets_for(ev["id"]):
            if m.get("closed"):
                continue
            print(f" • {m['question']}")
            for o in m.get("outcomes", []):
                price_cents = o["price"] * 100
                print(f"    └─ {o['name']:<20}: {price_cents:5.1f}¢")
        print()  # blank line between events


if __name__ == "__main__":
    while True:
        try:
            print_board(live_sports_events())
        except Exception as exc:
            print("⚠️  Error:", exc)
        time.sleep(REFRESH_SECONDS)
