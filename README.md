# Polymarket Sports Tracker

A real-time sports betting odds tracker for Polymarket, displaying live odds for MLB and NFL games.

## Description

This Python script connects to the Polymarket API to fetch and display live betting odds for sports events. It continuously monitors active sports markets and shows the current odds for various outcomes.

## Features

- 🏟️ Real-time odds tracking for sports events
- 📊 Clean, formatted display of betting markets
- 🔄 Automatic refresh every 60 seconds
- 🎯 Focuses on MLB and NFL games (easily extensible)
- ⚡ Error handling and connection recovery

## Requirements

```bash
pip install requests
```

## Usage

```bash
python "Import Poly Markets.py"
```

The script will start displaying live odds and refresh automatically every minute.

## Sample Output

```
==== 2024-01-15 18:30:45 UTC  — Polymarket live odds ====

🏟️  Yankees vs Red Sox  (eventId 12345)
 • Who will win the game?
    └─ Yankees              : 65.4¢
    └─ Red Sox              : 34.6¢

🏟️  Chiefs vs Bills  (eventId 67890)
 • Who will win the game?
    └─ Chiefs               : 58.2¢
    └─ Bills                : 41.8¢
```

## Configuration

- `REFRESH_SECONDS`: How often to update odds (default: 60 seconds)
- `SPORT_KEYWORDS`: Which sports to track (default: "mlb", "nfl")
- `BASE`: Polymarket API endpoint

## API Information

This script uses the Polymarket Gamma API:
- Events endpoint: `https://gamma-api.polymarket.com/events`
- Markets endpoint: `https://gamma-api.polymarket.com/markets`

## License

MIT License - feel free to modify and use as needed.
