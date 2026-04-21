"""
Satellite Passage Tracker Bot
==============================
Tracks the next 48h passages of ISS or Meteor M2-4 over a user-defined location.
Remembers the last used position and offers to reuse it at the start.

Dependencies:
    pip install "python-telegram-bot[job-queue]>=20" requests

Setup:
    1. Create a bot via @BotFather on Telegram → get BOT_TOKEN
    2. Get a free API key from https://www.n2yo.com/api/ → N2YO_API_KEY
    3. Set both in the CONFIGURATION section below (or as env vars).

Flow:
    /start → if previous location saved: ask reuse or new  (inline buttons)
           → if no previous location: ask for location directly
           → show satellite selection (inline buttons)
           → show next 48h passes
"""

import os
from dotenv import load_dotenv
import logging
import requests
from datetime import datetime, timezone
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
load_dotenv()
BOT_TOKEN    = os.getenv("BOT_TOKEN")
N2YO_API_KEY = os.getenv("N2YO_API_KEY")

N2YO_PASSES_URL = (
    "https://api.n2yo.com/rest/v1/satellite/radiopasses/{norad_id}"
    "/{lat}/{lon}/{alt}/{days}/10/&apiKey={key}"
)

# Satellites available for selection: display name → NORAD ID
SATELLITES = {
    "ISS": 25544,
    "Meteor M2-4": 59051,
}

# Minimum elevation (degrees) for a pass to be shown
MIN_ELEVATION = 10

# ─── CONVERSATION STATES ──────────────────────────────────────────────────────

ASK_REUSE_LOC, ASK_LOCATION, CHOOSE_SAT = range(3)

# ─── LOGGING ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _last_loc_key(user_id: int) -> str:
    return f"last_location_{user_id}"


def _save_location(user_id: int, context: ContextTypes.DEFAULT_TYPE,
                   lat: float, lon: float, alt: float = 0) -> None:
    """Persist the last used location in bot_data (survives across /start calls)."""
    context.bot_data[_last_loc_key(user_id)] = {"lat": lat, "lon": lon, "alt": alt}


def get_passes(norad_id: int, lat: float, lon: float, alt: float = 0) -> list[dict]:
    """Fetch next 48-hour radio passes from N2YO."""
    url = N2YO_PASSES_URL.format(
        norad_id=norad_id, lat=lat, lon=lon, alt=int(alt), days=2, key=N2YO_API_KEY
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("passes", []) or []
    except Exception as exc:
        logger.error("Passes fetch error: %s", exc)
        return []


def fmt_utc(ts: int) -> str:
    """Format a Unix timestamp as a readable UTC string."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d  %H:%M UTC")


def passes_message(sat_name: str, passes: list[dict]) -> str:
    """Build a formatted Markdown message listing upcoming passes."""
    if not passes:
        return (
            f"No passes above {MIN_ELEVATION} deg elevation found "
            f"for *{sat_name}* in the next 48 hours.\n"
            "Try again later or pick a different satellite."
        )

    lines = [f"Satellite: *{sat_name}*\nNext passes (48 h)\n"]
    for i, p in enumerate(passes, 1):
        max_el = p.get("maxEl", p.get("maxElevation", "?"))
        start  = fmt_utc(p["startUTC"])
        end    = fmt_utc(p["endUTC"])
        lines.append(
            f"*Pass {i}*\n"
            f"  Start:    `{start}`\n"
            f"  End:      `{end}`\n"
            f"  Max elev: `{max_el} deg`\n"
        )
    return "\n".join(lines)


def sat_selection_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard with one button per available satellite."""
    buttons = [
        [InlineKeyboardButton(label, callback_data=str(norad_id))]
        for label, norad_id in SATELLITES.items()
    ]
    return InlineKeyboardMarkup(buttons)


async def _ask_new_location(message, context) -> int:
    """Send the location-request message. Accepts a telegram Message object."""
    share_btn = KeyboardButton("Share my location", request_location=True)
    keyboard = ReplyKeyboardMarkup(
        [[share_btn]], resize_keyboard=True, one_time_keyboard=True
    )
    await message.reply_text(
        "Please share your location.\n"
        "Tap *Share my location*, or type coordinates like:\n"
        "`48.8566, 2.3522`",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return ASK_LOCATION


# ─── HANDLERS ─────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point - offer to reuse last position if one is saved."""
    context.user_data.clear()
    user_id = update.effective_user.id
    last = context.bot_data.get(_last_loc_key(user_id))

    if last:
        lat, lon = last["lat"], last["lon"]
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                f"Use last position ({lat:.4f}, {lon:.4f})",
                callback_data="use_last_loc",
            )],
            [InlineKeyboardButton("Enter a new position", callback_data="new_loc")],
        ])
        await update.message.reply_text(
            "Welcome back to *Satellite Tracker*!\n\n"
            "Would you like to use your last position?",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        return ASK_REUSE_LOC

    # First time — no saved location
    await update.message.reply_text(
        "Welcome to *Satellite Tracker*!", parse_mode="Markdown"
    )
    return await _ask_new_location(update.message, context)


async def handle_reuse_loc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the use-last-position / enter-new-position choice."""
    query = update.callback_query
    await query.answer()

    if query.data == "use_last_loc":
        user_id = update.effective_user.id
        last = context.bot_data[_last_loc_key(user_id)]
        context.user_data["lat"] = last["lat"]
        context.user_data["lon"] = last["lon"]
        context.user_data["alt"] = last.get("alt", 0)
        await query.edit_message_text(
            f"Using last position: `{last['lat']:.4f}, {last['lon']:.4f}`",
            parse_mode="Markdown",
        )
        await query.message.reply_text(
            "Which satellite do you want to track?",
            reply_markup=sat_selection_keyboard(),
        )
        return CHOOSE_SAT

    # "new_loc"
    await query.edit_message_text("Sure! Send me your new location.")
    return await _ask_new_location(query.message, context)


async def receive_location_gps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User shared GPS location."""
    loc = update.message.location
    lat, lon, alt = loc.latitude, loc.longitude, 0
    context.user_data.update({"lat": lat, "lon": lon, "alt": alt})
    _save_location(update.effective_user.id, context, lat, lon, alt)
    return await _show_sat_selection(update, context)


async def receive_location_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User typed coordinates."""
    text = update.message.text.strip()
    try:
        parts = [p.strip() for p in text.replace(";", ",").split(",")]
        lat, lon = float(parts[0]), float(parts[1])
        alt = float(parts[2]) if len(parts) > 2 else 0
    except (ValueError, IndexError):
        await update.message.reply_text(
            "Could not parse that. Please use `lat, lon` format, e.g. `48.8566, 2.3522`",
            parse_mode="Markdown",
        )
        return ASK_LOCATION

    context.user_data.update({"lat": lat, "lon": lon, "alt": alt})
    _save_location(update.effective_user.id, context, lat, lon, alt)
    return await _show_sat_selection(update, context)


async def _show_sat_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirm location and show satellite selection inline keyboard."""
    lat = context.user_data["lat"]
    lon = context.user_data["lon"]
    await update.message.reply_text(
        f"Location set: `{lat:.4f}, {lon:.4f}`\n\nWhich satellite do you want to track?",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    await update.message.reply_text(
        "Select a satellite:",
        reply_markup=sat_selection_keyboard(),
    )
    return CHOOSE_SAT


async def receive_sat_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User tapped a satellite button - fetch and display passes."""
    query = update.callback_query
    await query.answer()

    if query.data == "restart":
        await query.edit_message_text(
            "Which satellite do you want to track?",
            reply_markup=sat_selection_keyboard(),
        )
        return CHOOSE_SAT

    if query.data == "change_loc":
        await query.edit_message_text("Sure! Send me your new location.")
        return await _ask_new_location(query.message, context)

    norad_id = int(query.data)
    sat_name = next(
        (label for label, nid in SATELLITES.items() if nid == norad_id),
        f"NORAD {norad_id}",
    )

    lat = context.user_data["lat"]
    lon = context.user_data["lon"]
    alt = context.user_data.get("alt", 0)

    await query.edit_message_text(f"Fetching passes for *{sat_name}*...", parse_mode="Markdown")

    passes = get_passes(norad_id, lat, lon, alt)
    msg = passes_message(sat_name, passes)
    await query.edit_message_text(msg, parse_mode="Markdown")

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Track another satellite", callback_data="restart"),
            InlineKeyboardButton("Change location",         callback_data="change_loc"),
        ]
    ])
    await query.message.reply_text("What would you like to do next?", reply_markup=keyboard)
    return CHOOSE_SAT


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Cancelled. Type /start to begin again.", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_REUSE_LOC: [
                CallbackQueryHandler(handle_reuse_loc, pattern="^(use_last_loc|new_loc)$"),
            ],
            ASK_LOCATION: [
                MessageHandler(filters.LOCATION, receive_location_gps),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_location_text),
            ],
            CHOOSE_SAT: [
                CallbackQueryHandler(receive_sat_selection),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv)

    logger.info("Bot is running - press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()