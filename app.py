import os
import random
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from flask import Flask

app = Flask(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

last_update_id = 0


def telegram_send(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    try:
        r = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text
            },
            timeout=10
        )
        print("SEND:", r.status_code, r.text)
        return r
    except Exception as e:
        print("SEND ERROR:", e)


def make_prediction():
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    period = now.strftime("%Y%m%d%H%M")
    prediction = random.choice(["BIG", "SMALL"])

    return (
        "🔥 VEERGAME PREDICTION 🔥\n\n"
        f"🕐 TIME: {now.strftime('%H:%M:%S')}\n"
        f"🎯 PERIOD: {period}\n\n"
        f"📌 PREDICTION: {prediction}\n\n"
        "⚠️ Statistical/entertainment prediction only."
    )


def bot_listener():
    global last_update_idif text.startswith("/start"):
    telegram_send(
        chat_id,
        make_prediction()
    )

    print("BOT LISTENER STARTED")

    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"

            response = requests.get(
                url,
                params={
                    "offset": last_update_id + 1,
                    "timeout": 20
                },
                timeout=30
            )

            data = response.json()

            if not data.get("ok"):
                print("GET UPDATES ERROR:", data)
                time.sleep(5)
                continue

            for update in data.get("result", []):
                last_update_id = update["update_id"]

                message = update.get("message")

                if not message:
                    continue

                chat_id = message["chat"]["id"]
                text = message.get("text", "")

                print("MESSAGE:", text)

                if text.startswith("/start"):
                    telegram_send(
                        chat_id,
                        make_prediction()
                    )

        except Exception as e:
            print("LISTENER ERROR:", repr(e))
            time.sleep(5)


@app.route("/")
def home():
    return "VeerGame Predictor is running!"


@app.route("/test")
def test():
    return {
        "bot_token_present": bool(TOKEN),
        "channel_id_present": bool(CHANNEL_ID),
        "message": "Bot is running. Open Telegram and press Start."
    }


if __name__ == "__main__":
    print("APP STARTING")

    requests.get(
        f"https://api.telegram.org/bot{TOKEN}/deleteWebhook",
        params={"drop_pending_updates": True},
        timeout=10
    )

    print("TOKEN PRESENT:", bool(TOKEN))
    print("CHANNEL ID PRESENT:", bool(CHANNEL_ID))

    threading.Thread(
        target=bot_listener,
        daemon=True
    ).start()

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
