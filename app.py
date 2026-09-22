import os
import threading
import time
import requests
from flask import Flask

app = Flask(__name__)

TOKEN = os.environ.get("BOT_TOKEN")

chat_ids = set()


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

    except Exception as e:
        print("SEND ERROR:", repr(e))


def bot_listener():
    last_update_id = 0

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

                chat_ids.add(chat_id)

                text = message.get("text", "")

                print("MESSAGE:", text)

                if text.startswith("/start"):
                    telegram_send(
                        chat_id,
                        "✅ 5 SECOND TEST STARTED"
                    )

        except Exception as e:
            print("LISTENER ERROR:", repr(e))
            time.sleep(5)


def auto_hi():
    print("AUTO HI STARTED")

    while True:
        time.sleep(5)

        for chat_id in list(chat_ids):
            telegram_send(
                chat_id,
                "HI"
            )


@app.route("/")
def home():
    return "VeerGame Predictor is running!"


@app.route("/test")
def test():
    return {
        "bot_token_present": bool(TOKEN),
        "message": "5 second test bot is running."
    }


if __name__ == "__main__":

    print("APP STARTING")

    print("TOKEN PRESENT:", bool(TOKEN))

    threading.Thread(
        target=bot_listener,
        daemon=True
    ).start()

    threading.Thread(
        target=auto_hi,
        daemon=True
    ).start()

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )   
