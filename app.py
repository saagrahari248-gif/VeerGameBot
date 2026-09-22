import os
import json
import time
import threading
import requests

from flask import Flask, request, jsonify


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "@VeerGameBot369").strip()
BRIDGE_KEY = os.getenv("BRIDGE_KEY", "veerbridge").strip()

PORT = int(os.getenv("PORT", "10000"))

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# =========================================================
# APP
# =========================================================

app = Flask(__name__)


# =========================================================
# STATE
# =========================================================

history = []

last_processed_issue = None
current_prediction = None
current_prediction_issue = None

level = 1

wins = 0
losses = 0

rolling_entries = []

telegram_offset = 0

channel_message_id = None


# =========================================================
# BASIC HELPERS
# =========================================================

def big_small(number):
    try:
        n = int(number)

        if n >= 5:
            return "BIG"

        return "SMALL"

    except Exception:
        return None


def normalize_rows(rows):
    result = []

    if not isinstance(rows, list):
        return result

    seen = set()

    for row in rows:
        if not isinstance(row, dict):
            continue

        issue = str(row.get("issueNumber", "")).strip()
        number = str(row.get("number", "")).strip()

        if not issue or number == "":
            continue

        if issue in seen:
            continue

        seen.add(issue)

        result.append({
            "issueNumber": issue,
            "number": number,
            "color": row.get("color"),
            "premium": row.get("premium"),
            "sum": row.get("sum")
        })

    # Latest first
    result.sort(
        key=lambda x: int(x["issueNumber"])
        if x["issueNumber"].isdigit()
        else 0,
        reverse=True
    )

    return result


# =========================================================
# PREDICTION ENGINE
# =========================================================

def make_prediction(rows):
    """
    Statistical/pattern prediction only.

    Uses recent history and looks for historical patterns.
    If no useful pattern exists, returns a frequency-based
    signal. This is not a guaranteed prediction.
    """

    rows = normalize_rows(rows)

    if len(rows) < 5:
        return None

    sequence = []

    for row in rows:
        result = big_small(row["number"])

        if result:
            sequence.append(result)

    if len(sequence) < 5:
        return None

    # -----------------------------------------------------
    # Look for repeated historical patterns.
    # Newest result is sequence[0].
    # -----------------------------------------------------

    for pattern_length in range(5, 1, -1):

        if len(sequence) <= pattern_length:
            continue

        target = tuple(sequence[:pattern_length])

        followers = []

        for i in range(pattern_length, len(sequence)):

            older_pattern = tuple(
                sequence[i - pattern_length:i]
            )

            if older_pattern == target:
                followers.append(sequence[i])

        if followers:

            big_count = followers.count("BIG")
            small_count = followers.count("SMALL")

            if big_count > small_count:
                return "BIG"

            if small_count > big_count:
                return "SMALL"

    # -----------------------------------------------------
    # Recent frequency fallback
    # -----------------------------------------------------

    recent = sequence[:5]

    big_count = recent.count("BIG")
    small_count = recent.count("SMALL")

    if big_count > small_count:
        return "SMALL"

    if small_count > big_count:
        return "BIG"

    # Equal -> no forced signal
    return None


# =========================================================
# TELEGRAM
# =========================================================

def telegram_send_message(text):
    global channel_message_id

    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN missing", flush=True)
        return None

    try:
        response = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": CHANNEL_ID,
                "text": text
            },
            timeout=15
        )

        data = response.json()

        if not data.get("ok"):
            print(
                "TELEGRAM SEND ERROR:",
                data,
                flush=True
            )
            return None

        message_id = data["result"]["message_id"]

        channel_message_id = message_id

        return message_id

    except Exception as e:
        print(
            "TELEGRAM SEND EXCEPTION:",
            repr(e),
            flush=True
        )

        return None


def telegram_edit_message(message_id, text):
    if not BOT_TOKEN:
        return False

    try:
        response = requests.post(
            f"{TELEGRAM_API}/editMessageText",
            json={
                "chat_id": CHANNEL_ID,
                "message_id": message_id,
                "text": text
            },
            timeout=15
        )

        data = response.json()

        if data.get("ok"):
            return True

        print(
            "TELEGRAM EDIT ERROR:",
            data,
            flush=True
        )

        return False

    except Exception as e:
        print(
            "TELEGRAM EDIT EXCEPTION:",
            repr(e),
            flush=True
        )

        return False


# =========================================================
# FORMAT
# =========================================================

def format_entry(entry):
    issue = entry["issue"]
    prediction = entry["prediction"]
    status = entry["status"]

    if prediction == "BIG":
        prediction_icon = "🟢"
    else:
        prediction_icon = "🔴"

    if status == "WIN":
        result_icon = "✅"
    elif status == "LOSS":
        result_icon = "💔"
    else:
        result_icon = "🔮"

    return (
        f"🎯 {issue} - "
        f"{prediction_icon} {prediction} …… {result_icon}"
    )


def build_prediction_message():

    lines = []

    lines.append("💀✍🏼 UNDER 6 LEVEL FIXER ✍🏼💀")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("")

    if not rolling_entries:
        lines.append("⏳ Waiting for first prediction...")
        lines.append("")
    else:

        for entry in rolling_entries:
            lines.append(format_entry(entry))

        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(
        f"🔥 LEVEL : {level} / 6"
    )
    lines.append(
        f"💎 WIN : {wins}    💔 LOSS : {losses}"
    )
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


# =========================================================
# MESSAGE UPDATE
# =========================================================

def publish_message():

    global channel_message_id

    text = build_prediction_message()

    # First message
    if channel_message_id is None:

        message_id = telegram_send_message(text)

        if message_id:
            print(
                "TELEGRAM: FIRST PREDICTION MESSAGE CREATED",
                message_id,
                flush=True
            )

        return

    # Existing message
    edited = telegram_edit_message(
        channel_message_id,
        text
    )

    if edited:

        print(
            "TELEGRAM: PREDICTION MESSAGE UPDATED",
            flush=True
        )

    else:

        # If message cannot be edited, create a new one.
        message_id = telegram_send_message(text)

        if message_id:

            print(
                "TELEGRAM: NEW MESSAGE CREATED",
                message_id,
                flush=True
            )


# =========================================================
# PROCESS NEW GAME RESULT
# =========================================================

def process_prediction(rows):

    global history
    global last_processed_issue
    global current_prediction
    global current_prediction_issue
    global level
    global wins
    global losses
    global rolling_entries

    rows = normalize_rows(rows)

    if not rows:
        return

    history = rows

    latest = rows[0]

    latest_issue = latest["issueNumber"]
    latest_result = big_small(latest["number"])

    if not latest_result:
        return

    # -----------------------------------------------------
    # Ignore same period
    # -----------------------------------------------------

    if latest_issue == last_processed_issue:
        return

    print(
        "NEW RESULT:",
        latest_issue,
        latest_result,
        flush=True
    )

    # -----------------------------------------------------
    # First result after startup
    # No previous prediction to evaluate.
    # -----------------------------------------------------

    if last_processed_issue is None:

        last_processed_issue = latest_issue

        prediction = make_prediction(rows)

        if prediction is None:
            print(
                "PREDICTION: WAIT - not enough pattern information",
                flush=True
            )
            return

        try:
            next_issue = str(int(latest_issue) + 1)
        except Exception:
            next_issue = latest_issue + "+1"

        current_prediction = prediction
        current_prediction_issue = next_issue

        rolling_entries.append({
            "issue": next_issue,
            "prediction": prediction,
            "status": "NEXT"
        })

        publish_message()

        print(
            "FIRST PREDICTION:",
            next_issue,
            prediction,
            flush=True
        )

        return

    # -----------------------------------------------------
    # Evaluate previous prediction
    # -----------------------------------------------------

    if (
        current_prediction_issue
        and latest_issue == current_prediction_issue
        and current_prediction
    ):

        if current_prediction == latest_result:

            wins += 1

            # WIN resets simulation level
            level = 1

            status = "WIN"

            print(
                "RESULT: WIN",
                latest_issue,
                current_prediction,
                latest_result,
                flush=True
            )

        else:

            losses += 1

            # Increase simulation level
            level = min(level + 1, 6)

            status = "LOSS"

            print(
                "RESULT: LOSS",
                latest_issue,
                current_prediction,
                latest_result,
                "LEVEL:",
                level,
                flush=True
            )

        # Update matching entry
        for entry in rolling_entries:

            if entry["issue"] == latest_issue:

                entry["status"] = status
                break

    # -----------------------------------------------------
    # This result is now processed
    # -----------------------------------------------------

    last_processed_issue = latest_issue

    # -----------------------------------------------------
    # Make next prediction
    # -----------------------------------------------------

    prediction = make_prediction(rows)

    if prediction is None:

        current_prediction = None
        current_prediction_issue = None

        publish_message()

        print(
            "NEXT PREDICTION: WAIT",
            flush=True
        )

        return

    try:
        next_issue = str(int(latest_issue) + 1)

    except Exception:
        next_issue = latest_issue + "+1"

    current_prediction = prediction
    current_prediction_issue = next_issue

    # -----------------------------------------------------
    # Rolling 10 entries
    # -----------------------------------------------------

    rolling_entries.append({
        "issue": next_issue,
        "prediction": prediction,
        "status": "NEXT"
    })

    # Keep only latest 10
    if len(rolling_entries) > 10:
        rolling_entries = rolling_entries[-10:]

    publish_message()

    print(
        "NEXT PREDICTION:",
        next_issue,
        prediction,
        "LEVEL:",
        level,
        flush=True
    )


# =========================================================
# BRIDGE
# =========================================================

@app.route("/push-history", methods=["POST"])
def push_history():

    try:

        key = request.form.get("key", "")
        payload_text = request.form.get("payload", "")

        if key != BRIDGE_KEY:
            return jsonify({
                "ok": False,
                "error": "invalid key"
            }), 403

        if not payload_text:
            return jsonify({
                "ok": False,
                "error": "missing payload"
            }), 400

        payload = json.loads(payload_text)

        rows = payload.get("list", [])

        rows = normalize_rows(rows)

        if not rows:

            return jsonify({
                "ok": True,
                "history_count": 0
            })

        print(
            "HISTORY RECEIVED:",
            len(rows),
            "LATEST:",
            rows[0]["issueNumber"],
            flush=True
        )

        process_prediction(rows)

        return jsonify({
            "ok": True,
            "history_count": len(rows),
            "latest": rows[0],
            "prediction": current_prediction,
            "prediction_issue": current_prediction_issue,
            "level": level,
            "wins": wins,
            "losses": losses
        })

    except Exception as e:

        print(
            "PUSH HISTORY ERROR:",
            repr(e),
            flush=True
        )

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


# =========================================================
# TEST / STATUS
# =========================================================

@app.route("/")
def home():

    return jsonify({
        "ok": True,
        "service": "VeerGame Predictor",
        "running": True
    })


@app.route("/test")
def test():

    return jsonify({
        "ok": True,
        "running": True,
        "history_count": len(history),
        "last_update": int(time.time() * 1000),
        "prediction": current_prediction,
        "prediction_issue": current_prediction_issue,
        "level": level,
        "wins": wins,
        "losses": losses,
        "entries": rolling_entries
    })


@app.route("/history")
def get_history():

    return jsonify({
        "ok": True,
        "count": len(history),
        "list": history
    })


# =========================================================
# TELEGRAM COMMANDS
# =========================================================

def telegram_get_updates():

    global telegram_offset

    if not BOT_TOKEN:
        return []

    try:

        response = requests.get(
            f"{TELEGRAM_API}/getUpdates",
            params={
                "offset": telegram_offset,
                "timeout": 20
            },
            timeout=30
        )

        data = response.json()

        if not data.get("ok"):
            return []

        return data.get("result", [])

    except Exception as e:

        print(
            "TELEGRAM UPDATE ERROR:",
            repr(e),
            flush=True
        )

        return []


def telegram_reply(chat_id, text):

    try:

        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text
            },
            timeout=15
        )

    except Exception as e:

        print(
            "TELEGRAM REPLY ERROR:",
            repr(e),
            flush=True
        )


def telegram_listener():

    global telegram_offset

    print(
        "TELEGRAM LISTENER STARTED",
        flush=True
    )

    while True:

        try:

            updates = telegram_get_updates()

            for update in updates:

                telegram_offset = update["update_id"] + 1

                message = update.get("message")

                if not message:
                    continue

                chat_id = message["chat"]["id"]

                text = message.get("text", "").strip()

                if text == "/start":

                    telegram_reply(
                        chat_id,
                        "✅ Owner connected.\n"
                        "💀 Under 6 Level Fixer is running."
                    )

                elif text == "/status":

                    telegram_reply(
                        chat_id,
                        "💻 VEERGAME STATUS\n\n"
                        f"🔥 Level: {level}/6\n"
                        f"💎 Wins: {wins}\n"
                        f"💔 Losses: {losses}\n"
                        f"🎯 Prediction: "
                        f"{current_prediction or 'WAIT'}\n"
                        f"🎯 Period: "
                        f"{current_prediction_issue or 'WAIT'}"
                    )

                elif text == "/history":

                    if not rolling_entries:

                        telegram_reply(
                            chat_id,
                            "⏳ No prediction history yet."
                        )

                    else:

                        lines = [
                            "💀 LAST 10 PREDICTIONS",
                            "━━━━━━━━━━━━━━━━━━━━"
                        ]

                        for entry in rolling_entries:
                            lines.append(
                                format_entry(entry)
                            )

                        telegram_reply(
                            chat_id,
                            "\n".join(lines)
                        )

                elif text == "/reset":

                    telegram_reply(
                        chat_id,
                        "ℹ️ Reset is disabled in this version."
                    )

        except Exception as e:

            print(
                "TELEGRAM LISTENER ERROR:",
                repr(e),
                flush=True
            )

        time.sleep(1)


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    print("==============================", flush=True)
    print("VEERGAME PREDICTOR STARTING", flush=True)
    print("==============================", flush=True)

    print(
        "TOKEN PRESENT:",
        bool(BOT_TOKEN),
        flush=True
    )

    print(
        "CHANNEL:",
        CHANNEL_ID,
        flush=True
    )

    if not BOT_TOKEN:

        print(
            "WARNING: BOT_TOKEN is missing",
            flush=True
        )

    listener_thread = threading.Thread(
        target=telegram_listener,
        daemon=True
    )

    listener_thread.start()

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False
        )
