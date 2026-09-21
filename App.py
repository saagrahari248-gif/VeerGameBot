import os
import random
from flask import Flask, request

app = Flask(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

last_results = []
level = 1
wins = 0
losses = 0


def send_message(text):
    import requests

    if not TOKEN or not CHANNEL_ID:
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    requests.post(
        url,
        json={
            "chat_id": CHANNEL_ID,
            "text": text
        },
        timeout=15
    )


def make_prediction():
    return random.choice(["BIG", "SMALL"])


def statistics():
    total = wins + losses

    lines = ["🔥 STATISTICS | LAST 20 PERIODS 🔥", ""]

    for item in last_results[-20:]:
        lines.append(
            f"🕐 {item['time']} : Period {item['period']} — "
            f"{item['prediction']} — {item['result']}"
        )

    lines.append("")
    lines.append(f"📊 TOTAL: {wins} WIN | {losses} LOSS")

    if total:
        rate = round((wins / total) * 100, 1)
    else:
        rate = 0

    lines.append(f"🎯 WIN RATE: {rate}%")
    lines.append(f"📈 CURRENT LEVEL: {level}")

    return "\n".join(lines)


@app.route("/")
def home():
    return "VeerGame Predictor Bot is running!"


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)

    if data:
        print(data)

    return "OK"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
