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

# Alert configuration via environment variables
ALERT_DELTA_CENTS = float(os.getenv("ALERT_DELTA_CENTS", "2.0"))
ALERT_ONLY_QUESTIONS = set(q.strip().lower() for q in (os.getenv("ALERT_ONLY_QUESTIONS", "").split("||")) if q.strip())
ALERT_EVENT_SLUGS = set(s.strip() for s in (os.getenv("ALERT_EVENT_SLUGS", "").split(",")) if s.strip())


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


def poll_nfl_events_for_date(target_date: dt.date, max_iterations: int | None = None):
    """Continuously poll NFL events for the given date and print odds when priced."""
    events = find_nfl_events_for_date(target_date)
    if ALERT_EVENT_SLUGS:
        events = [ev for ev in events if (ev.get("slug") or "") in ALERT_EVENT_SLUGS]
    event_ids = [str(ev["id"]) for ev in events]
    print(f"Polling {len(event_ids)} NFL events for {target_date} — {', '.join(event_ids)}")

    # Memory of last seen prices per (eventId, marketId, outcomeName)
    last_seen: dict[tuple[str, str, str], float] = {}

    iteration = 0
    while True:
        iteration += 1
        timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"\n==== {timestamp} — NFL odds for {target_date} (iteration {iteration}) ====\n")

        any_printed = False
        for ev in events:
            ev_id = str(ev["id"])
            try:
                mkts = markets_for(ev_id)
            except Exception as exc:
                print(f"⚠️  Error fetching markets for event {ev_id}: {exc}")
                continue

            open_active = [m for m in mkts if not m.get("closed") and m.get("active", True)]
            priced_pairs: list[tuple[str, str, list[tuple[str, float]]]] = []
            for m in open_active:
                question = m.get("question", f"market {m.get('id')}")
                if ALERT_ONLY_QUESTIONS and question.lower() not in ALERT_ONLY_QUESTIONS:
                    continue
                pairs = _parse_outcomes_and_prices(m)
                if pairs:
                    priced_pairs.append((str(m.get("id")), question, pairs))

            if priced_pairs:
                any_printed = True
                print(f"🏟️  {ev.get('title')}  (eventId {ev_id})")
                for market_id, question, pairs in priced_pairs:
                    print(f" • {question}")
                    for outcome_name, price in pairs:
                        key = (ev_id, market_id, outcome_name)
                        price_cents = price * 100.0
                        previous = last_seen.get(key)
                        if previous is None or abs(price_cents - previous) >= ALERT_DELTA_CENTS:
                            print(f"    └─ {outcome_name:<20}: {price_cents:5.1f}¢")
                            last_seen[key] = price_cents
                print()
            else:
                print(f"(no priced open markets yet) {ev.get('title')}  (eventId {ev_id})")

        if max_iterations is not None and iteration >= max_iterations:
            break
        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    # Optional: single-run mode to list NFL games for a given date
    date_env = os.getenv("NFL_DATE")  # format YYYY-MM-DD
    if date_env and os.getenv("NFL_POLL") != "1":
        try:
            target = dt.date.fromisoformat(date_env)
        except Exception:
            raise SystemExit(f"Invalid NFL_DATE: {date_env}")
        events = find_nfl_events_for_date(target)
        print(f"Found {len(events)} NFL events for {date_env}")
        for ev in events:
            print(f" - {ev.get('id')}: {ev.get('title')}  (slug {ev.get('slug')})")
        raise SystemExit(0)

    # Optional: polling mode for NFL date
    if date_env and os.getenv("NFL_POLL") == "1":
        try:
            target = dt.date.fromisoformat(date_env)
        except Exception:
            raise SystemExit(f"Invalid NFL_DATE: {date_env}")
        max_iters_env = os.getenv("NFL_MAX_ITERS")
        max_iters = int(max_iters_env) if (max_iters_env and max_iters_env.isdigit()) else None
        poll_nfl_events_for_date(target, max_iterations=max_iters)
        raise SystemExit(0)

    while True:
        try:
            print_board(live_sports_events())
        except Exception as exc:
            print("⚠️  Error:", exc)
        time.sleep(REFRESH_SECONDS)
