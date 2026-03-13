import asyncio
import json
import websockets
import requests
import nest_asyncio
import os

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

nest_asyncio.apply()

BOT_TOKEN = os.getenv("BOT_TOKEN")

chat_keywords = {}
chat_track_all = {}

# --------------------------
# COMMANDS
# --------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    chat_keywords.setdefault(chat_id, set())
    chat_track_all.setdefault(chat_id, False)

    await update.message.reply_text(
        "🚀 BAPU Tracker Active\n\n"
        "/track keyword\n"
        "/trackall\n"
        "/stop keyword\n"
        "/stopall\n"
        "/list"
    )

async def track(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text("Usage: /track keyword")
        return

    word = context.args[0].lower()

    chat_keywords.setdefault(chat_id, set())
    chat_keywords[chat_id].add(word)

    chat_track_all[chat_id] = False

    await update.message.reply_text(f"Tracking keyword: {word}")

async def trackall(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id
    chat_track_all[chat_id] = True

    await update.message.reply_text("Tracking ALL tokens")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    if not context.args:
        return

    word = context.args[0].lower()

    if word in chat_keywords.get(chat_id, set()):
        chat_keywords[chat_id].remove(word)

async def stopall(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id
    chat_keywords[chat_id] = set()
    chat_track_all[chat_id] = False

async def list_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    keys = chat_keywords.get(chat_id, set())

    if not keys:
        await update.message.reply_text("No keywords tracked")
        return

    text = "\n".join(keys)

    await update.message.reply_text(text)

# --------------------------
# MARKETCAP
# --------------------------

def calculate_marketcap(data):

    try:

        sol_reserve = float(data.get("virtualSolReserves", 0))
        token_reserve = float(data.get("virtualTokenReserves", 0))

        if sol_reserve == 0 or token_reserve == 0:
            return "N/A"

        price = sol_reserve / token_reserve

        supply = 1_000_000_000

        mc = price * supply

        if mc > 1_000_000:
            return f"${mc/1_000_000:.2f}M"
        elif mc > 1_000:
            return f"${mc/1_000:.2f}K"
        else:
            return f"${mc:.0f}"

    except:
        return "N/A"

# --------------------------
# SEND MESSAGE
# --------------------------

def send_message(chat_id, message, mint):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    keyboard = {
        "inline_keyboard": [[
            {"text": "🚀 Pump", "url": f"https://pump.fun/coin/{mint}"},
            {"text": "📈 Dexscreener", "url": f"https://dexscreener.com/solana/{mint}"}
        ]]
    }

    requests.post(url, json={
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "reply_markup": keyboard
    })

# --------------------------
# LISTENER
# --------------------------

async def listen():

    uri = "wss://pumpportal.fun/api/data"

    while True:

        try:

            async with websockets.connect(uri) as ws:

                await ws.send(json.dumps({
                    "method": "subscribeNewToken"
                }))

                print("Listening for launches...")

                while True:

                    msg = await ws.recv()

                    raw = json.loads(msg)

                    data = raw.get("data", raw)

                    name = data.get("name","")
                    symbol = data.get("symbol","")
                    mint = data.get("mint","")

                    if not mint:
                        continue

                    bonding = data.get("bondingCurveProgress","N/A")

                    marketcap = calculate_marketcap(data)

                    text = (name + " " + symbol).lower()

                    message = f"""
🚀 *NEW TOKEN*

*Name:* {name}
*Symbol:* {symbol}

💰 *Marketcap:* {marketcap}

📋 *CA*
`{mint}`

📈 *Bonding:* {bonding}%
"""

                    all_chats = set(chat_keywords.keys()) | set(chat_track_all.keys())

                    for chat_id in all_chats:

                        if chat_track_all.get(chat_id):

                            send_message(chat_id, message, mint)

                        else:

                            for k in chat_keywords.get(chat_id,set()):

                                if k in text:
                                    send_message(chat_id, message, mint)
                                    break

        except Exception as e:

            print("Reconnect:", e)

            await asyncio.sleep(5)

# --------------------------
# MAIN
# --------------------------

async def main():

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track))
    app.add_handler(CommandHandler("trackall", trackall))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("stopall", stopall))
    app.add_handler(CommandHandler("list", list_keywords))

    asyncio.create_task(listen())

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
