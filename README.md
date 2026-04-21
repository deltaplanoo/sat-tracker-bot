# 🛰 Satellite Tracker Bot

A Telegram bot that retrieves the next 48-hour satellite passages over any location, with inline button navigation and GPS support.

---

## Features

- 📍 Location input via GPS share **or** typed coordinates
- 🔍 Live satellite search (any name/partial name)
- 🎛 Inline button selection from matched results
- 🕐 Next 48-hour passes with start time, end time, and max elevation
- 🔄 Restart inline button to track another satellite

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Get your tokens

| Token | Where to get it |
|-------|----------------|
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) on Telegram — `/newbot` |
| `N2YO_API_KEY` | [https://www.n2yo.com/api/](https://www.n2yo.com/api/) — free registration |

### 3. Configure

Either edit the script directly:

```python
BOT_TOKEN    = "123456:ABCdef..."
N2YO_API_KEY = "XXXXX-XXXXX-XXXXX-XXXXX"
```

Or set environment variables (recommended):

```bash
export BOT_TOKEN="123456:ABCdef..."
export N2YO_API_KEY="XXXXX-XXXXX-XXXXX-XXXXX"
python satellite_tracker_bot.py
```

---

## Conversation flow

```
/start
  └─► Ask for location
        ├─ [📍 Share my location]  ← GPS button
        └─ Type "lat, lon"  e.g. 43.7696, 11.2558

  └─► Show next 48h passes:
        Pass 1
          🕐 Start : 2025-03-15  18:42 UTC
          🕑 End   : 2025-03-15  18:48 UTC
          📐 Max El: 72°

  └─► [🔄 Track another satellite]
```

---

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot / restart the flow |
| `/cancel` | Cancel current conversation |

---

## Notes

- The N2YO free tier allows **1 000 API transactions/hour** — plenty for personal use.
- Passes with a maximum elevation below **10°** are filtered out by default (configurable via `MIN_ELEVATION`).
- The bot requests `radiopasses` from N2YO, which covers all tracked satellites, not just visually observable ones.
