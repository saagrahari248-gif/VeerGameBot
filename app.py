import os
from flask import Flask, request, jsonify

app = Flask(__name__)

BRIDGE_KEY = os.environ.get("BRIDGE_KEY", "veerbridge")

latest_history = []
last_update = None


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Bridge-Key"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.route("/")
def home():
    return "VeerGame Browser Bridge is running"


@app.route("/push-history", methods=["POST", "OPTIONS"])
def push_history():

    if request.method == "OPTIONS":
        return "", 204

    key = request.headers.get("X-Bridge-Key")

    if key != BRIDGE_KEY:
        return jsonify({
            "ok": False,
            "error": "Invalid bridge key"
        }), 401

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "ok": False,
            "error": "No JSON received"
        }), 400

    rows = data.get("list", [])

    if not isinstance(rows, list):
        return jsonify({
            "ok": False,
            "error": "Invalid history format"
        }), 400

    global latest_history, last_update

    latest_history = rows
    last_update = data.get("timestamp")

    return jsonify({
        "ok": True,
        "history_count": len(latest_history),
        "latest": latest_history[0] if latest_history else None
    })


@app.route("/history")
def history():

    return jsonify({
        "ok": True,
        "history_count": len(latest_history),
        "last_update": last_update,
        "list": latest_history
    })


@app.route("/test")
def test():

    return jsonify({
        "running": True,
        "history_count": len(latest_history),
        "latest": latest_history[0] if latest_history else None
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(
        host="0.0.0.0",
        port=port
    )
