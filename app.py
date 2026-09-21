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

LEVEL = 1
HISTORY = []


def send_telegram(message):
    if not TOKEN or not CHANNEL_ID:
        print("BOT_TOKEN or CHANNEL_ID missing")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    try:
        response = requests.post(
            url,
            json={
                "chat_id": CHANNEL_ID,
                "text": message
            },
            timeout=15
        )

        print("Telegram response:", response.status_code, response.text)

    except Exception as e:
        print("Telegram error:", e)


def get_prediction():
    return random.choice(["BIG", "SMALL"])


def make_period(now):
    return now.strftime("%Y%m%d%H%M")


def send_prediction():
    now = datetime.now(ZoneInfo("Asia/Kolkata"))

    period = make_period(now)
    prediction = get_prediction()

    HISTORY.append({
        "period": period,
        "prediction": prediction,
        "time": now.strftime("%H:%M")
    })

    if len(HISTORY) > 20:
        HISTORY.pop(0)

    message = (
        "🔥 VEERGAME PREDICTION 🔥\n\n"
        f"🕐 TIME: {now.strftime('%H:%M')}\n"
        f"🎯 PERIOD: {period}\n\n"
        f"📌 PREDICTION: {prediction}\n"
        f"📈 LEVEL: {LEVEL}\n\n"
        "⚠️ Statistical/entertainment prediction only."
    )

    send_telegram(message)
    print(message)


def scheduler():
    last_minute = ""

    while True:
        try:
            now = datetime.now(ZoneInfo("Asia/Kolkata"))
            current_minute = now.strftime("%Y-%m-%d %H:%M")

            # 24 घंटे, हर मिनट
            if current_minute != last_minute:
                last_minute = current_minute
                send_prediction()

            time.sleep(5)

        except Exception as e:
            print("Scheduler error:", e)
            time.sleep(10)


@app.route("/")
def home():
    return "VeerGame Predictor is running!"


@app.route("/test")
def test():
    send_prediction()
    return "Test prediction sent"


@app.route("/history")
def history():
    return {
        "level": LEVEL,
        "history": HISTORY
    }


if __name__ == "__main__":
    threading.Thread(target=scheduler, daemon=True).start()

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
