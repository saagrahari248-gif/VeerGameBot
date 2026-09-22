import os
import requests
from flask import Flask

app = Flask(__name__)

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
                "pageSize": 500,
                "ts": 1790053617323
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json,text/plain,*/*",
                "Referer": "https://www.91apph.com/"
            },
            timeout=20
        )

        return {
            "status_code": r.status_code,
            "content_type": r.headers.get("content-type"),
            "length": len(r.text),
            "first_500_chars": r.text[:500]
        }

    except Exception as e:

        return {
            "error": repr(e)
        }


if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
