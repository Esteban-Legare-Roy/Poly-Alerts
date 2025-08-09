"""
real_time_polymarket_sports.py
--------------------------------
Display live Polymarket odds for every open MLB or NFL game.
Requires: pip install requests
"""

import requests, time, datetime as dt, json
import os

BASE = "https://gamma-api.polymarket.com"
REFRESH_SECONDS = 60
SPORT_KEYWORDS = ("mlb", "nfl")        # extend to nba, epl, etc. if desired

NFL_TEAM_ABBRS = [
    "ari","atl","bal","buf","car","chi","cin","cle","dal","den",
    "det","gb","hou","ind","jax","kc","lv","lac","lar","mia",
    "min","ne","no","nyg","nyj","phi","pit","sea","sf","tb",
    "ten","wsh"
]


def live_sports_events() -> list[dict]:
    """Return all active MLB & NFL events (games)."""
    r = requests.get(f"{BASE}/events", params={"active": "true"}, timeout=10)
    r.raise_for_status()
    events = r.json()
    print(f"DEBUG: Found {len(events)} total events")
    
    # Filter to sports category
    sports_events = [e for e in events if "sports" in (e.get("category") or "").lower()]
    print(f"DEBUG: Found {len(sports_events)} sports events")

    # Filter by sport keywords in title (e.g., mlb, nfl)
    filtered = []
    for event in sports_events:
        title_lower = (event.get("title") or "").lower()
        if any(keyword in title_lower for keyword in SPORT_KEYWORDS):
            filtered.append(event)
    print(f"DEBUG: Filtered to {len(filtered)} events matching {SPORT_KEYWORDS}")

    return filtered


def markets_for(event_id: str) -> list[dict]:
    """Return markets attached to an event."""
    r = requests.get(f"{BASE}/markets", params={"eventId": event_id}, timeout=10)
    r.raise_for_status()
    return r.json()


def find_nfl_events_for_date(target_date: dt.date) -> list[dict]:
    """Discover NFL events by brute-forcing slugs for the given date.

    Slug pattern: nfl-{away}-{home}-{YYYY-MM-DD}
    Returns a list of unique event dicts.
    """
    discovered_by_id: dict[str, dict] = {}
    date_str = target_date.isoformat()

    for away in NFL_TEAM_ABBRS:
        for home in NFL_TEAM_ABBRS:
            if away == home:
                continue
            slug = f"nfl-{away}-{home}-{date_str}"
            try:
                resp = requests.get(f"{BASE}/events", params={"slug": slug}, timeout=7)
                if resp.status_code != 200:
                    continue
                events = resp.json()
                if isinstance(events, list) and events:
                    ev = events[0]
                    ev_id = str(ev.get("id"))
                    discovered_by_id[ev_id] = ev
            except Exception:
                continue
            # tiny pacing to avoid hitting any rate limits
            time.sleep(0.02)

    return list(discovered_by_id.values())


def _parse_outcomes_and_prices(market: dict) -> list[tuple[str, float]]:
    """Return list of (outcome_name, price_float_0_to_1) for a market.

    The Gamma API often returns 'outcomes' and 'outcomePrices' as stringified JSON arrays.
    This function handles both string and list forms.
    """
    outcomes_raw = market.get("outcomes")
    prices_raw = market.get("outcomePrices")

    # Parse outcomes
    if isinstance(outcomes_raw, str):
        try:
            outcomes_list = json.loads(outcomes_raw)
        except Exception:
            outcomes_list = []
    elif isinstance(outcomes_raw, list):
        outcomes_list = outcomes_raw
    else:
        outcomes_list = []

    # Parse prices
    if isinstance(prices_raw, str):
        try:
            prices_list = json.loads(prices_raw)
        except Exception:
            prices_list = []
    elif isinstance(prices_raw, list):
        prices_list = prices_raw
    else:
        prices_list = []

    # Normalize price strings to floats
    normalized_prices: list[float] = []
    for p in prices_list:
        try:
            normalized_prices.append(float(p))
        except Exception:
            normalized_prices.append(0.0)

    # Pair outcomes with prices; if lengths mismatch, truncate to shortest
    paired: list[tuple[str, float]] = []
    for name, price in zip(outcomes_list, normalized_prices):
        # Some APIs may include dict outcomes; keep only the name string
        if isinstance(name, dict):
            name = name.get("name") or "Unknown"
        paired.append((str(name), float(price)))

    return paired


def print_board(events: list[dict]):
    """Pretty-print prices for every event/market/outcome."""
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n==== {timestamp}  — Polymarket live odds ====\n")

    for ev in events:
        print(f"🏟️  {ev['title']}  (eventId {ev['id']})")
        for m in markets_for(ev["id"]):
            # Only show active, open markets
            if m.get("closed") or not m.get("active", True):
                continue
            print(f" • {m['question']}")
            for outcome_name, price in _parse_outcomes_and_prices(m):
                price_cents = price * 100
                print(f"    └─ {outcome_name:<20}: {price_cents:5.1f}¢")
        print()  # blank line between events


if __name__ == "__main__":
    # Optional: single-run mode to list NFL games for a given date
    date_env = os.getenv("NFL_DATE")  # format YYYY-MM-DD
    if date_env:
        try:
            target = dt.date.fromisoformat(date_env)
        except Exception:
            raise SystemExit(f"Invalid NFL_DATE: {date_env}")
        events = find_nfl_events_for_date(target)
        print(f"Found {len(events)} NFL events for {date_env}")
        for ev in events:
            print(f" - {ev.get('id')}: {ev.get('title')}  (slug {ev.get('slug')})")
        raise SystemExit(0)

    while True:
        try:
            print_board(live_sports_events())
        except Exception as exc:
            print("⚠️  Error:", exc)
        time.sleep(REFRESH_SECONDS)
