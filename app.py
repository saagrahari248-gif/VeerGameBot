import os
import random
import requests
from flask import Flask

app = Flask(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

level = 1
wins = 0
losses = 0
history = []


def send_message(text):
    if not TOKEN or not CHANNEL_ID:
        print("BOT_TOKEN or CHANNEL_ID missing")
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


@app.route("/")
def home():
    return "VeerGame Predictor is running!"


@app.route("/test")
def test():
    prediction = make_prediction()

    message = (
        "🔥 VEERGAME PREDICTION 🔥\n\n"
        f"🎯 PREDICTION: {prediction}\n"
        f"📈 LEVEL: {level}\n"
        f"📊 WIN: {wins} | LOSS: {losses}\n\n"
        "⚠️ Prediction is for entertainment/statistical tracking only."
    )

    send_message(message)
    return "Test prediction sent"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
