import os
import time
import threading
import requests

from flask import Flask, request, jsonify


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@VeerGameBot369")
BRIDGE_KEY = os.environ.get("BRIDGE_KEY", "veerbridge")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Flask(__name__)


# =========================================================
# SHARED DATA
# =========================================================

history = []
last_history_update = 0

last_processed_issue = None

current_prediction = None
current_prediction_issue = None

wins = 0
losses = 0
level = 1

bot_running = True

telegram_offset = 0


# =========================================================
# BIG / SMALL
# =========================================================

def big_small(number):
    try:
        n = int(number)

        if n >= 5:
            return "BIG"

        return "SMALL"

    except Exception:
        return None


# =========================================================
# TELEGRAM
# =========================================================

def telegram_send(text):
    try:
        response = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": CHANNEL_ID,
                "text": text
            },
            timeout=15
        )

        return response.ok

    except Exception as e:
        print("TELEGRAM SEND ERROR:", repr(e))
        return False


def telegram_get_updates():
    global telegram_offset

    try:
        response = requests.get(
            f"{TELEGRAM_API}/getUpdates",
            params={
                "offset": telegram_offset,
                "timeout": 10
            },
            timeout=20
        )

        if not response.ok:
            return []

        data = response.json()

        if not data.get("ok"):
            return []

        return data.get("result", [])

    except Exception as e:
        print("TELEGRAM UPDATE ERROR:", repr(e))
        return []


# =========================================================
# PREDICTION ENGINE
# =========================================================

def make_prediction(rows):
    """
    Uses the latest 15 BIG/SMALL results.

    The API list is newest -> oldest.

    We search historical sequences from longer to shorter.
    If the same sequence appeared earlier, we look at what
    result followed it historically.

    If no useful historical continuation exists, return WAIT.
    """

    if len(rows) < 15:
        return None

    newest_first = []

    for row in rows[:15]:
        value = big_small(row.get("number"))

        if value:
            newest_first.append(value)

    if len(newest_first) < 15:
        return None

    # Convert to oldest -> newest
    sequence = list(reversed(newest_first))

    # Search longest pattern first
    for pattern_length in range(7, 0, -1):

        target = sequence[-pattern_length:]

        followers = []

        # Look through older history
        for i in range(0, len(sequence) - pattern_length):

            part = sequence[i:i + pattern_length]

            if part == target:

                next_index = i + pattern_length

                if next_index < len(sequence):
                    followers.append(sequence[next_index])

        if followers:

            big_count = followers.count("BIG")
            small_count = followers.count("SMALL")

            if big_count > small_count:
                return "BIG"

            if small_count > big_count:
                return "SMALL"

    return None


# =========================================================
# RESULT PROCESSING
# =========================================================

def process_prediction(rows):
    global last_processed_issue
    global current_prediction
    global current_prediction_issue
    global wins
    global losses
    global level

    if not rows:
        return

    latest = rows[0]

    issue = latest.get("issueNumber")
    number = latest.get("number")

    if not issue or number is None:
        return

    # Already processed this period
    if issue == last_processed_issue:
        return

    last_processed_issue = issue

    actual = big_small(number)

    print(
        "NEW RESULT:",
        issue,
        number,
        actual
    )

    # -----------------------------------------------------
    # Check previous prediction
    # -----------------------------------------------------

    if (
        current_prediction
        and current_prediction_issue
        and current_prediction_issue != issue
    ):

        if current_prediction == actual:

            wins += 1

            # Reset simulation level after WIN
            level = 1

            result_text = (
                "✅ SIMULATION WIN\n\n"
                f"Period: {current_prediction_issue}\n"
                f"Prediction: {current_prediction}\n"
                f"Result: {actual}\n\n"
                f"Total WIN: {wins}\n"
                f"Total LOSS: {losses}\n"
                f"Level: {level}"
            )

        else:

            losses += 1

            # Move to next simulation level
            if level < 7:
                level += 1

            result_text = (
                "❌ SIMULATION LOSS\n\n"
                f"Period: {current_prediction_issue}\n"
                f"Prediction: {current_prediction}\n"
                f"Result: {actual}\n\n"
                f"Total WIN: {wins}\n"
                f"Total LOSS: {losses}\n"
                f"Next level: {level}"
            )

        print(result_text)

        telegram_send(result_text)

    # -----------------------------------------------------
    # Make prediction for next period
    # -----------------------------------------------------

    prediction = make_prediction(rows)

    if prediction:

        try:
            next_issue = str(int(issue) + 1)
        except Exception:
            next_issue = "NEXT"

        current_prediction = prediction
        current_prediction_issue = next_issue

        prediction_text = (
            "🎯 VEERGAME ANALYSIS\n\n"
            f"Next Period: {next_issue}\n"
            f"Prediction: {prediction}\n"
            f"Analysis Level: {level}\n\n"
            f"WIN: {wins} | LOSS: {losses}\n"
            f"Mode: Simulation"
        )

        print(prediction_text)

        telegram_send(prediction_text)

    else:

        current_prediction = None
        current_prediction_issue = None

        telegram_send(
            "⏳ VEERGAME ANALYSIS\n\n"
            "Next period: WAIT\n"
            "Reason: No sufficiently supported historical pattern."
        )


# =========================================================
# BROWSER BRIDGE
# =========================================================

@app.route("/")
def home():
    return "VeerGame Predictor is running"


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
            "error": "Invalid history"
        }), 400

    global history
    global last_history_update

    history = rows
    last_history_update = data.get("timestamp", int(time.time() * 1000))

    print(
        "HISTORY RECEIVED:",
        len(history)
    )

    # Process immediately
    try:
        process_prediction(history)
    except Exception as e:
        print(
            "PROCESS ERROR:",
            repr(e)
        )

    return jsonify({
        "ok": True,
        "history_count": len(history),
        "latest": history[0] if history else None
    })


@app.route("/history")
def get_history():

    return jsonify({
        "ok": True,
        "history_count": len(history),
        "last_update": last_history_update,
        "list": history
    })


@app.route("/test")
def test():

    return jsonify({
        "running": bot_running,
        "history_count": len(history),
        "last_update": last_history_update,
        "prediction": current_prediction,
        "prediction_issue": current_prediction_issue,
        "wins": wins,
        "losses": losses,
        "level": level
    })


# =========================================================
# TELEGRAM COMMAND LISTENER
# =========================================================

def telegram_listener():

    global telegram_offset

    print("TELEGRAM LISTENER STARTED")

    while True:

        updates = telegram_get_updates()

        for update in updates:

            telegram_offset = update["update_id"] + 1

            message = update.get("message")

            if not message:
                continue

            text = message.get("text", "")

            chat = message.get("chat", {})

            chat_id = chat.get("id")

            if not text or not chat_id:
                continue

            if text.startswith("/start"):

                requests.post(
                    f"{TELEGRAM_API}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": (
                            "✅ VeerGame Predictor connected.\n\n"
                            "Commands:\n"
                            "/status\n"
                            "/history\n"
                            "/reset"
                        )
                    },
                    timeout=15
                )

            elif text.startswith("/status"):

                requests.post(
                    f"{TELEGRAM_API}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": (
                            "📊 STATUS\n\n"
                            f"Prediction: {current_prediction}\n"
                            f"Period: {current_prediction_issue}\n"
                            f"WIN: {wins}\n"
                            f"LOSS: {losses}\n"
                            f"Level: {level}\n"
                            f"History: {len(history)}"
                        )
                    },
                    timeout=15
                )

            elif text.startswith("/history"):

                recent = history[:15]

                lines = []

                for row in recent:

                    issue = row.get("issueNumber")
                    number = row.get("number")
                    bs = big_small(number)

                    lines.append(
                        f"{issue} → {number} → {bs}"
                    )

                requests.post(
                    f"{TELEGRAM_API}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": (
                            "📜 LAST RESULTS\n\n"
                            + "\n".join(lines)
                        )
                    },
                    timeout=15
                )

            elif text.startswith("/reset"):

                reset_state()

                requests.post(
                    f"{TELEGRAM_API}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": "♻️ Simulation statistics reset."
                    },
                    timeout=15
                )


# =========================================================
# RESET
# =========================================================

def reset_state():

    global wins
    global losses
    global level
    global current_prediction
    global current_prediction_issue
    global last_processed_issue

    wins = 0
    losses = 0
    level = 1

    current_prediction = None
    current_prediction_issue = None

    last_processed_issue = None


# =========================================================
# START BACKGROUND LISTENER
# =========================================================

def start_background_threads():

    thread = threading.Thread(
        target=telegram_listener,
        daemon=True
    )

    thread.start()


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    print("================================")
    print("VEERGAME PREDICTOR STARTING")
    print("================================")

    print(
        "TOKEN PRESENT:",
        bool(BOT_TOKEN)
    )

    print(
        "CHANNEL:",
        CHANNEL_ID
    )

    start_background_threads()

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
