import os
import time
import threading
import requests
from flask import Flask

app = Flask(__name__)

# =========================
# SETTINGS
# =========================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@VeerGameBot369")

HISTORY_URL = (
    "https://draw.ar-lottery01.com/"
    "WinGo/WinGo_1M/GetHistoryIssuePage.json"
)

CURRENT_URL = (
    "https://draw.ar-lottery01.com/"
    "WinGo/WinGo_1M.json"
)

POLL_SECONDS = 5

# =========================
# STATE
# =========================

owner_chat_id = None

last_completed_issue = None
last_prediction_issue = None

prediction = None
prediction_message_id = None

level = 1
wins = 0
losses = 0

history_cache = []


# =========================
# TELEGRAM API
# =========================

def telegram_api(method, data):

    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN missing")
        return None

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"

    try:
        response = requests.post(
            url,
            json=data,
            timeout=15
        )

        result = response.json()

        print(
            "TELEGRAM:",
            method,
            response.status_code,
            result.get("ok")
        )

        return result

    except Exception as e:

        print(
            "TELEGRAM ERROR:",
            repr(e)
        )

        return None


def send_message(chat_id, text):

    return telegram_api(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text
        }
    )


def edit_message(chat_id, message_id, text):

    return telegram_api(
        "editMessageText",
        {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text
        }
    )


# =========================
# GET GAME HISTORY
# =========================

def get_history():

    try:

        response = requests.get(
            HISTORY_URL,
            params={
                "pageNo": 1,
                "pageSize": 500,
                "ts": int(time.time() * 1000)
            },
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            timeout=15
        )

        print(
            "HISTORY API:",
            response.status_code
        )

        data = response.json()

        if data.get("code") != 0:

            print(
                "HISTORY API ERROR:",
                data
            )

            return []

        rows = (
            data
            .get("data", {})
            .get("list", [])
        )

        print(
            "HISTORY COUNT:",
            len(rows)
        )

        result = []

        for row in rows:

            issue = str(
                row.get(
                    "issueNumber",
                    ""
                )
            )

            number_text = str(
                row.get(
                    "number",
                    ""
                )
            )

            if not issue or number_text == "":
                continue

            try:

                number = int(
                    number_text
                )

            except:

                continue

            size = (
                "BIG"
                if number >= 5
                else "SMALL"
            )

            result.append(
                {
                    "issue": issue,
                    "number": number,
                    "size": size,
                    "color": row.get(
                        "color",
                        ""
                    )
                }
            )

        print(
            "VALID HISTORY:",
            len(result)
        )

        return result

    except Exception as e:

        print(
            "HISTORY REQUEST ERROR:",
            repr(e)
        )

        return []


# =========================
# GET CURRENT PERIOD
# =========================

def get_periods():

    try:

        response = requests.get(
            CURRENT_URL,
            params={
                "ts": int(time.time() * 1000)
            },
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            timeout=15
        )

        print(
            "PERIOD API:",
            response.status_code
        )

        data = response.json()

        previous = data.get(
            "previous",
            {}
        )

        current = data.get(
            "current",
            {}
        )

        next_data = data.get(
            "next",
            {}
        )

        result = {

            "previous": str(
                previous.get(
                    "issueNumber",
                    ""
                )
            ),

            "current": str(
                current.get(
                    "issueNumber",
                    ""
                )
            ),

            "next": str(
                next_data.get(
                    "issueNumber",
                    ""
                )
            )
        }

        print(
            "PERIODS:",
            result
        )

        return result

    except Exception as e:

        print(
            "PERIOD REQUEST ERROR:",
            repr(e)
        )

        return {
            "previous": "",
            "current": "",
            "next": ""
        }


# =========================
# PREDICTION STRATEGY
# =========================

def make_prediction(history):

    if len(history) < 15:

        print(
            "WAIT: History less than 15:",
            len(history)
        )

        return None, (
            "15 results required"
        )

    # API newest -> oldest
    # Strategy oldest -> newest

    sequence = [
        item["size"]
        for item in reversed(history)
    ]

    recent_15 = sequence[-15:]

    print(
        "LAST 15:",
        " ".join(recent_15)
    )

    # Pattern length 7 -> 1

    for pattern_length in range(
        7,
        0,
        -1
    ):

        target = recent_15[
            -pattern_length:
        ]

        continuations = []

        for i in range(
            0,
            len(sequence) - pattern_length
        ):

            old_pattern = sequence[
                i:i + pattern_length
            ]

            if old_pattern == target:

                next_index = (
                    i + pattern_length
                )

                if next_index < len(sequence):

                    continuations.append(
                        sequence[next_index]
                    )

        if not continuations:
            continue

        big_count = (
            continuations.count("BIG")
        )

        small_count = (
            continuations.count("SMALL")
        )

        print(
            "PATTERN:",
            pattern_length,
            "BIG:",
            big_count,
            "SMALL:",
            small_count
        )

        if big_count > small_count:

            return (
                "BIG",
                f"Pattern {pattern_length}: "
                f"BIG {big_count}, "
                f"SMALL {small_count}"
            )

        if small_count > big_count:

            return (
                "SMALL",
                f"Pattern {pattern_length}: "
                f"BIG {big_count}, "
                f"SMALL {small_count}"
            )

    return (
        None,
        "No strong historical continuation"
    )


# =========================
# CHANNEL MESSAGE
# =========================

def prediction_text(issue, pred):

    return (
        "🎯 VEER GAME PREDICTION\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"Period: {issue}\n"
        f"Prediction: {pred}\n"
        f"Level: {level}/7\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "⏳ Result ka wait..."
    )


def result_text(
    issue,
    number,
    actual,
    pred,
    status
):

    return (
        "🎯 VEER GAME RESULT\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"Period: {issue}\n"
        f"Number: {number}\n"
        f"Actual: {actual}\n"
        f"Prediction: {pred}\n"
        f"Result: {status}\n"
        f"Level: {level}/7\n"
        f"Wins: {wins}\n"
        f"Losses: {losses}\n"
        "━━━━━━━━━━━━━━━━━━"
    )


def post_channel(text):

    global prediction_message_id

    result = send_message(
        CHANNEL_ID,
        text
    )

    if result and result.get("ok"):

        try:

            prediction_message_id = (
                result["result"]["message_id"]
            )

            print(
                "CHANNEL MESSAGE SENT:",
                prediction_message_id
            )

        except Exception as e:

            print(
                "MESSAGE ID ERROR:",
                repr(e)
            )

    else:

        print(
            "CHANNEL SEND FAILED:",
            result
        )


def update_channel(text):

    global prediction_message_id

    if not prediction_message_id:

        post_channel(text)
        return

    result = edit_message(
        CHANNEL_ID,
        prediction_message_id,
        text
    )

    if not result or not result.get("ok"):

        print(
            "EDIT FAILED, SENDING NEW MESSAGE"
        )

        post_channel(text)


# =========================
# GAME PROCESS
# =========================

def process_game():

    global history_cache
    global last_completed_issue
    global last_prediction_issue
    global prediction

    global level
    global wins
    global losses

    history = get_history()

    if not history:

        print(
            "NO HISTORY RECEIVED"
        )

        return

    periods = get_periods()

    next_period = periods["next"]

    if not next_period:

        print(
            "NEXT PERIOD NOT FOUND"
        )

        return

    latest = history[0]

    completed_issue = latest["issue"]
    completed_number = latest["number"]
    completed_size = latest["size"]

    history_cache = history

    # =========================
    # FIRST START
    # =========================

    if last_completed_issue is None:

        last_completed_issue = (
            completed_issue
        )

        print(
            "STARTED FROM:",
            completed_issue,
            completed_number,
            completed_size
        )

        pred, reason = make_prediction(
            history
        )

        print(
            "FIRST PREDICTION:",
            pred,
            reason
        )

        if pred:

            prediction = {
                "issue": next_period,
                "prediction": pred,
                "reason": reason
            }

            last_prediction_issue = (
                next_period
            )

            post_channel(
                prediction_text(
                    next_period,
                    pred
                )
            )

        return

    # =========================
    # NEW COMPLETED RESULT
    # =========================

    if completed_issue != last_completed_issue:

        print(
            "NEW RESULT:",
            completed_issue,
            completed_number,
            completed_size
        )

        # Check previous prediction

        if prediction:

            predicted_issue = (
                prediction["issue"]
            )

            if predicted_issue == completed_issue:

                pred = prediction[
                    "prediction"
                ]

                if pred == completed_size:

                    status = "WIN"

                    wins += 1

                    # WIN -> reset level
                    level = 1

                else:

                    status = "LOSS"

                    losses += 1

                    # Simulation level
                    if level < 7:
                        level += 1

                print(
                    "RESULT:",
                    status,
                    "LEVEL:",
                    level,
                    "WINS:",
                    wins,
                    "LOSSES:",
                    losses
                )

                update_channel(
                    result_text(
                        completed_issue,
                        completed_number,
                        completed_size,
                        pred,
                        status
                    )
                )

        last_completed_issue = (
            completed_issue
        )

        prediction = None

    # =========================
    # NEXT PREDICTION
    # =========================

    if next_period:

        if next_period != last_prediction_issue:

            pred, reason = make_prediction(
                history
            )

            print(
                "NEXT PREDICTION:",
                next_period,
                pred,
                reason
            )

            if pred:

                prediction = {
                    "issue": next_period,
                    "prediction": pred,
                    "reason": reason
                }

                last_prediction_issue = (
                    next_period
                )

                update_channel(
                    prediction_text(
                        next_period,
                        pred
                    )
                )

            else:

                print(
                    "WAIT:",
                    next_period,
                    reason
                )


# =========================
# GAME LOOP
# =========================

def game_loop():

    print(
        "GAME LOOP STARTED"
    )

    while True:

        try:

            process_game()

        except Exception as e:

            print(
                "GAME LOOP ERROR:",
                repr(e)
            )

        time.sleep(
            POLL_SECONDS
        )


# =========================
# TELEGRAM LISTENER
# =========================

def bot_listener():

    global owner_chat_id

    offset = 0

    print(
        "BOT LISTENER STARTED"
    )

    while True:

        try:

            url = (
                f"https://api.telegram.org/"
                f"bot{BOT_TOKEN}/getUpdates"
            )

            response = requests.get(
                url,
                params={
                    "offset": offset + 1,
                    "timeout": 20
                },
                timeout=30
            )

            data = response.json()

            if not data.get("ok"):

                print(
                    "UPDATE ERROR:",
                    data
                )

                time.sleep(5)
                continue

            for update in data.get(
                "result",
                []
            ):

                offset = update[
                    "update_id"
                ]

                message = update.get(
                    "message"
                )

                if not message:
                    continue

                chat_id = message[
                    "chat"
                ]["id"]

                text = message.get(
                    "text",
                    ""
                ).strip()

                # First /start = owner

                if owner_chat_id is None:

                    if text.startswith(
                        "/start"
                    ):

                        owner_chat_id = (
                            chat_id
                        )

                        send_message(
                            chat_id,
                            "✅ Owner connected.\n"
                            "VeerGame Predictor running."
                        )

                        print(
                            "OWNER:",
                            owner_chat_id
                        )

                    continue

                # Ignore other users

                if chat_id != owner_chat_id:
                    continue

                if text.startswith(
                    "/start"
                ):

                    send_message(
                        chat_id,
                        "✅ BOT RUNNING\n\n"
                        f"Level: {level}/7\n"
                        f"Wins: {wins}\n"
                        f"Losses: {losses}"
                    )

                elif text.startswith(
                    "/status"
                ):

                    send_message(
                        chat_id,
                        "📊 STATUS\n"
                        "━━━━━━━━━━━━\n"
                        f"Level: {level}/7\n"
                        f"Wins: {wins}\n"
                        f"Losses: {losses}\n"
                        f"Prediction: {prediction}"
                    )

                elif text.startswith(
                    "/history"
                ):

                    lines = []

                    for item in history_cache[:15]:

                        lines.append(
                            f"{item['issue']} | "
                            f"{item['number']} | "
                            f"{item['size']}"
                        )

                    if lines:

                        send_message(
                            chat_id,
                            "📚 LAST 15\n\n"
                            + "\n".join(lines)
                        )

                    else:

                        send_message(
                            chat_id,
                            "History available nahi hai."
                        )

                elif text.startswith(
                    "/reset"
                ):

                    level = 1
                    wins = 0
                    losses = 0

                    send_message(
                        chat_id,
                        "♻️ Simulation reset.\n"
                        "Level: 1/7"
                    )

        except Exception as e:

            print(
                "LISTENER ERROR:",
                repr(e)
            )

            time.sleep(5)


# =========================
# WEB
# =========================

@app.route("/")
def home():

    return (
        "VeerGame Predictor is running!"
    )


@app.route("/test")
def test():

    return {
        "running": True,
        "token_present": bool(BOT_TOKEN),
        "channel": CHANNEL_ID,
        "level": level,
        "wins": wins,
        "losses": losses,
        "history_count": len(
            history_cache
        ),
        "prediction": prediction
    }


# =========================
# START
# =========================

if __name__ == "__main__":

    print(
        "================================"
    )

    print(
        "VEERGAME PREDICTOR STARTING"
    )

    print(
        "================================"
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
        target=bot_listener,
        daemon=True
    ).start()

    threading.Thread(
        target=game_loop,
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
