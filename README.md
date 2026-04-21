# 🛰 Satellite Tracker Bot

A Telegram bot that retrieves the next 48-hour satellite passages over any location, with inline button navigation and GPS support.

---

## Features

- 📍 Location input via GPS share **or** typed coordinates
- 🔍 Live satellite search (any name/partial name)
- 🎛 Inline button selection from matched results
- 🕐 Next 48-hour passes with start time, end time, and max elevation
- 🔄 Restart inline button to track another satellite

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
