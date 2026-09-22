import os
import time
import threading
import requests
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@VeerGameBot369")
BRIDGE_KEY = os.environ.get("BRIDGE_KEY", "veerbridge")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

history = []
last_history_update = 0

last_processed_issue = None
current_prediction = None
current_prediction_issue = None

wins = 0
losses = 0
level = 1

telegram_offset = 0


# =========================
# CORS
# =========================

@app.after_request
def cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


# =========================
# BIG / SMALL
# =========================

def big_small(number):

    try:
        return "BIG" if int(number) >= 5 else "SMALL"

    except Exception:
        return None


# =========================
# TELEGRAM SEND
# =========================

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

        print(
            "TELEGRAM:",
            response.status_code,
            response.text[:300]
        )

        return response.ok

    except Exception as e:

        print(
            "TELEGRAM ERROR:",
            repr(e)
        )

        return False


# =========================
# PREDICTION
# =========================

def make_prediction(rows):

    if len(rows) < 5:
        return None

    sequence = []

    for row in rows:

        result = big_small(
            row.get("number")
        )

        if result:
            sequence.append(result)

    if len(sequence) < 5:
        return None

    # API newest -> oldest
    # Convert to oldest -> newest
    sequence = list(reversed(sequence))

    print(
        "ANALYSIS SEQUENCE:",
        sequence
    )

    # --------------------------------
    # Pattern search
    # --------------------------------

    for length in range(
        min(5, len(sequence) - 1),
        1,
        -1
    ):

        target = sequence[-length:]

        followers = []

        for i in range(
            len(sequence) - length
        ):

            if sequence[
                i:i + length
            ] == target:

                next_index = i + length

                if next_index < len(sequence):

                    followers.append(
                        sequence[next_index]
                    )

        if followers:

            big_count = followers.count(
                "BIG"
            )

            small_count = followers.count(
                "SMALL"
            )

            print(
                "PATTERN:",
                target,
                "FOLLOWERS:",
                followers
            )

            if big_count > small_count:
                return "BIG"

            if small_count > big_count:
                return "SMALL"

    # --------------------------------
    # Recent frequency fallback
    # --------------------------------

    recent = sequence[-5:]

    big_count = recent.count(
        "BIG"
    )

    small_count = recent.count(
        "SMALL"
    )

    if big_count > small_count:
        return "SMALL"

    if small_count > big_count:
        return "BIG"

    return None


# =========================
# PROCESS RESULT
# =========================

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

    issue = latest.get(
        "issueNumber"
    )

    number = latest.get(
        "number"
    )

    if not issue or number is None:
        return

    # Same result already processed
    if issue == last_processed_issue:
        return

    last_processed_issue = issue

    actual = big_small(
        number
    )

    print(
        "NEW RESULT:",
        issue,
        number,
        actual
    )

    # =========================
    # CHECK PREVIOUS PREDICTION
    # =========================

    if current_prediction:

        if current_prediction == actual:

            wins += 1

            level = 1

            telegram_send(
                "✅ RESULT\n\n"
                f"Period: {current_prediction_issue}\n"
                f"Prediction: {current_prediction}\n"
                f"Result: {actual}\n\n"
                f"WIN: {wins} | LOSS: {losses}\n"
                f"Level: {level}"
            )

        else:

            losses += 1

            if level < 7:
                level += 1

            telegram_send(
                "❌ RESULT\n\n"
                f"Period: {current_prediction_issue}\n"
                f"Prediction: {current_prediction}\n"
                f"Result: {actual}\n\n"
                f"WIN: {wins} | LOSS: {losses}\n"
                f"Next Level: {level}"
            )

    # =========================
    # NEW PREDICTION
    # =========================

    prediction = make_prediction(
        rows
    )

    try:

        next_issue = str(
            int(issue) + 1
        )

    except Exception:

        next_issue = "NEXT"

    if prediction:

        current_prediction = prediction

        current_prediction_issue = next_issue

        telegram_send(
            "🎯 VEERGAME PREDICTION\n\n"
            f"Next Period: {next_issue}\n"
            f"Prediction: {prediction}\n\n"
            f"Level: {level}\n"
            f"WIN: {wins} | LOSS: {losses}\n\n"
            "Mode: Statistical Simulation"
        )

        print(
            "PREDICTION:",
            next_issue,
            prediction
        )

    else:

        current_prediction = None

        current_prediction_issue = None

        print(
            "NO CLEAR PREDICTION"
        )


# =========================
# BRIDGE
# =========================

@app.route(
    "/push-history",
    methods=["POST"]
)
def push_history():

    global history
    global last_history_update

    key = request.form.get(
        "key"
    )

    if key != BRIDGE_KEY:

        return jsonify({
            "ok": False,
            "error": "Invalid bridge key"
        }), 401

    payload = request.form.get(
        "payload"
    )

    if not payload:

        return jsonify({
            "ok": False,
            "error": "No payload"
        }), 400

    try:

        data = json.loads(
            payload
        )

    except Exception as e:

        return jsonify({
            "ok": False,
            "error": "Invalid JSON",
            "detail": str(e)
        }), 400

    rows = data.get(
        "list",
        []
    )

    if not isinstance(
        rows,
        list
    ):

        return jsonify({
            "ok": False,
            "error": "Invalid history"
        }), 400

    history = rows

    last_history_update = data.get(
        "timestamp",
        int(time.time() * 1000)
    )

    print(
        "HISTORY RECEIVED:",
        len(history)
    )

    try:

        process_prediction(
            history
        )

    except Exception as e:

        print(
            "PROCESS ERROR:",
            repr(e)
        )

    return jsonify({
        "ok": True,
        "history_count": len(history),
        "latest": (
            history[0]
            if history
            else None
        )
    })


# =========================
# TEST
# =========================

@app.route("/test")
def test():

    return jsonify({
        "running": True,
        "history_count": len(history),
        "last_update": last_history_update,
        "prediction": current_prediction,
        "prediction_issue": current_prediction_issue,
        "wins": wins,
        "losses": losses,
        "level": level
    })


# =========================
# HISTORY
# =========================

@app.route("/history")
def get_history():

    return jsonify({
        "ok": True,
        "history_count": len(history),
        "last_update": last_history_update,
        "list": history
    })


# =========================
# TELEGRAM COMMANDS
# =========================

def telegram_listener():

    global telegram_offset

    print(
        "TELEGRAM LISTENER STARTED"
    )

    while True:

        try:

            response = requests.get(
                f"{TELEGRAM_API}/getUpdates",
                params={
                    "offset": telegram_offset,
                    "timeout": 10
                },
                timeout=20
            )

            data = response.json()

            if not data.get(
                "ok"
            ):

                time.sleep(2)
                continue

            for update in data.get(
                "result",
                []
            ):

                telegram_offset = (
                    update["update_id"] + 1
                )

                message = update.get(
                    "message"
                )

                if not message:
                    continue

                text = message.get(
                    "text",
                    ""
                )

                chat_id = message.get(
                    "chat",
                    {}
                ).get(
                    "id"
                )

                if not text or not chat_id:
                    continue

                if text.startswith(
                    "/start"
                ):

                    requests.post(
                        f"{TELEGRAM_API}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text":
                                "✅ VeerGame Predictor connected.\n\n"
                                "/status\n"
                                "/history\n"
                                "/reset"
                        },
                        timeout=15
                    )

                elif text.startswith(
                    "/status"
                ):

                    requests.post(
                        f"{TELEGRAM_API}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text":
                                "📊 STATUS\n\n"
                                f"Prediction: {current_prediction}\n"
                                f"Period: {current_prediction_issue}\n"
                                f"WIN: {wins}\n"
                                f"LOSS: {losses}\n"
                                f"Level: {level}\n"
                                f"History: {len(history)}"
                        },
                        timeout=15
                    )

                elif text.startswith(
                    "/history"
                ):

                    lines = []

                    for row in history:

                        issue = row.get(
                            "issueNumber"
                        )

                        number = row.get(
                            "number"
                        )

                        result = big_small(
                            number
                        )

                        lines.append(
                            f"{issue} → {number} → {result}"
                        )

                    requests.post(
                        f"{TELEGRAM_API}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text":
                                "📜 HISTORY\n\n"
                                + "\n".join(lines)
                        },
                        timeout=15
                    )

                elif text.startswith(
                    "/reset"
                ):

                    reset_state()

                    requests.post(
                        f"{TELEGRAM_API}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text":
                                "♻️ Simulation reset."
                        },
                        timeout=15
                    )

        except Exception as e:

            print(
                "TELEGRAM ERROR:",
                repr(e)
            )

            time.sleep(3)


# =========================
# RESET
# =========================

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


# =========================
# START
# =========================

if __name__ == "__main__":

    print(
        "=============================="
    )

    print(
        "VEERGAME PREDICTOR STARTING"
    )

    print(
        "=============================="
    )

    print(
        "TOKEN PRESENT:",
        bool(BOT_TOKEN)
    )

    print(
        "CHANNEL:",
        CHANNEL_ID
    )

    threading.Thread(
        target=telegram_listener,
        daemon=True
    ).start()

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
