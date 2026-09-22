import os
import requests
from flask import Flask

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@VeerGameBot369")

HISTORY_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json"


@app.route("/")
def home():
    return "Bot is running"


@app.route("/test")
def test():

    try:
        r = requests.get(
            HISTORY_URL,
            params={
                "pageNo": 1,
                "pageSize": 500
            },
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            timeout=20
        )

        data = r.json()

        rows = data.get("data", {}).get("list", [])

        return {
            "status_code": r.status_code,
            "api_code": data.get("code"),
            "history_count": len(rows),
            "first_result": rows[0] if rows else None
        }

    except Exception as e:

        return {
            "error": repr(e)
        }


if __name__ == "__main__":

    print("TEST SERVER STARTING")
    print("TOKEN:", bool(BOT_TOKEN))
    print("CHANNEL:", CHANNEL_ID)

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
