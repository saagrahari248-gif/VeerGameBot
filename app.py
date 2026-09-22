import os
import time
import threading
import requests
from flask import Flask

app = Flask(__name__)

# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")

CHANNEL_ID = os.environ.get("CHANNEL_ID", "@VeerGameBot369")

# Optional:
# Telegram owner ka numeric chat ID yahan environment variable me rakho.
# Agar empty hai to bot commands sabse pehle /start karne wale chat ko
# owner maan lega.
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID", "")

HISTORY_URL = (
    "https://draw.ar-lottery01.com/"
    "WinGo/WinGo_1M/GetHistoryIssuePage.json"
)

CURRENT_URL = (
    "https://draw.ar-lottery01.com/"
    "WinGo/WinGo_1M.json"
)

POLL_SECONDS = 5

# =========================================================
# MEMORY
# =========================================================

owner_chat_id = int(OWNER_CHAT_ID) if OWNER_CHAT_ID.isdigit() else None

last_completed_issue = None
last_prediction_issue = None

prediction = None
prediction_message_id = None

simulation_level = 1
win_count = 0
loss_count = 0

box_win_count = 0

history_cache = []

lock = threading.Lock()


# =========================================================
# TELEGRAM
# =========================================================

def telegram_request(method, payload):
    if not BOT_TOKEN:
        print("BOT_TOKEN missing")
        return None

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"

    try:
        r = requests.post(
            url,
            json=payload,
            timeout=15
        )

        print("TELEGRAM:", method, r.status_code)

        if not r.ok:
            print(r.text)

        return r.json()

    except Exception as e:
        print("TELEGRAM ERROR:", repr(e))
        return None


def telegram_send(chat_id, text):
    return telegram_request(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text
        }
    )


def telegram_edit(chat_id, message_id, text):
    return telegram_request(
        "editMessageText",
        {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text
        }
    )


# =========================================================
# GAME API
# =========================================================

def get_history():
    try:
        r = requests.get(
            HISTORY_URL,
            params={
                "ts": int(time.time() * 1000)
            },
            timeout=15
        )

        data = r.json()

        if data.get("code") != 0:
            print("HISTORY API ERROR:", data)
            return []

        rows = data.get("data", {}).get("list", [])

        result = []

        for row in rows:

            issue = str(row.get("issueNumber", ""))
            number_text = str(row.get("number", ""))

            if not issue or number_text == "":
                continue

            try:
                number = int(number_text)
            except:
                continue

            # 0-4 SMALL
            # 5-9 BIG
            size = "BIG" if number >= 5 else "SMALL"

            result.append(
                {
                    "issue": issue,
                    "number": number,
                    "size": size,
                    "color": row.get("color", "")
                }
            )

        return result

    except Exception as e:
        print("HISTORY ERROR:", repr(e))
        return []


def get_current_period():
    try:
        r = requests.get(
            CURRENT_URL,
            params={
                "ts": int(time.time() * 1000)
            },
            timeout=15
        )

        data = r.json()

        current = data.get("current", {})
        next_period = data.get("next", {})
        previous = data.get("previous", {})

        return {
            "previous": str(previous.get("issueNumber", "")),
            "current": str(current.get("issueNumber", "")),
            "next": str(next_period.get("issueNumber", ""))
        }

    except Exception as e:
        print("CURRENT API ERROR:", repr(e))
        return {
            "previous": "",
            "current": "",
            "next": ""
        }


# =========================================================
# STRATEGY
# =========================================================

def build_sequence(history):
    """
    API latest -> oldest hota hai.
    Hum oldest -> newest sequence banate hain.
    """

    ordered = list(reversed(history))

    return [
        item["size"]
        for item in ordered
    ]


def pattern_prediction(history):
    """
    Last 15 completed results use karta hai.

    Strategy:
    - Last 15 BIG/SMALL dekho.
    - Recent suffix ke same patterns history me search karo.
    - Pattern ke baad historically BIG/SMALL kya aaya,
      uska majority continuation lo.
    - Pattern na mile to WAIT.

    Yeh statistical simulation hai, guaranteed prediction nahi.
    """

    if len(history) < 15:
        return None, "15 results available nahi hain"

    sequence = build_sequence(history)

    recent = sequence[-15:]

    # Longer pattern ko priority
    for pattern_length in range(7, 0, -1):

        if len(sequence) <= pattern_length:
            continue

        target = recent[-pattern_length:]

        continuations = []

        # Historical sequence me matching pattern dhundo.
        # Current last pattern ko exclude karne ke liye
        # sirf older positions check kar rahe hain.
        for i in range(0, len(sequence) - pattern_length):

            pattern = sequence[i:i + pattern_length]

            if pattern == target:

                next_index = i + pattern_length

                if next_index < len(sequence):
                    continuations.append(
                        sequence[next_index]
                    )

        if continuations:

            big_count = continuations.count("BIG")
            small_count = continuations.count("SMALL")

            if big_count > small_count:
                return (
                    "BIG",
                    f"Pattern length {pattern_length}, "
                    f"historical BIG {big_count} / SMALL {small_count}"
                )

            if small_count > big_count:
                return (
                    "SMALL",
                    f"Pattern length {pattern_length}, "
                    f"historical BIG {big_count} / SMALL {small_count}"
                )

    # No strong continuation
    return None, "Matching historical continuation nahi mila"


# =========================================================
# MESSAGE FORMAT
# =========================================================

def make_prediction_message(
    issue,
    pred,
    reason,
    level
):
    return (
        "🎯 VEER GAME PREDICTION\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"Period: {issue}\n"
        f"Prediction: {pred}\n"
        f"Level: {level}/7\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Status: WAITING FOR RESULT\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Pattern analysis only — no guaranteed result."
    )


def make_result_message(
    issue,
    number,
    actual,
    pred,
    status,
    level
):
    return (
        "🎯 VEER GAME RESULT\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"Period: {issue}\n"
        f"Number: {number}\n"
        f"Actual: {actual}\n"
        f"Prediction: {pred}\n"
        f"Result: {status}\n"
        f"Simulation Level: {level}/7\n"
        "━━━━━━━━━━━━━━━━━━"
    )


# =========================================================
# CHANNEL POSTING
# =========================================================

def send_new_channel_message(text):
    global prediction_message_id

    result = telegram_send(
        CHANNEL_ID,
        text
    )

    try:
        if result and result.get("ok"):
            prediction_message_id = (
                result["result"]["message_id"]
            )
    except:
        pass


def edit_channel_message(text):
    global prediction_message_id

    if not prediction_message_id:
        send_new_channel_message(text)
        return

    result = telegram_edit(
        CHANNEL_ID,
        prediction_message_id,
        text
    )

    if not result or not result.get("ok"):
        send_new_channel_message(text)


# =========================================================
# GAME PROCESSING
# =========================================================

def process_new_game_state():
    global history_cache
    global last_completed_issue
    global last_prediction_issue
    global prediction

    global simulation_level
    global win_count
    global loss_count
    global box_win_count
    global prediction_message_id

    history = get_history()

    if not history:
        print("No history")
        return

    current_data = get_current_period()

    current_period = current_data.get("current", "")
    next_period = current_data.get("next", "")

    if not current_period:
        print("Current period not found")
        return

    history_cache = history

    latest = history[0]

    completed_issue = latest["issue"]
    completed_number = latest["number"]
    completed_size = latest["size"]

    # -----------------------------------------------------
    # FIRST RUN
    # -----------------------------------------------------

    if last_completed_issue is None:

        last_completed_issue = completed_issue

        print(
            "BOT STARTED FROM ISSUE:",
            completed_issue
        )

        # First prediction
        if next_period:

            pred, reason = pattern_prediction(history)

            if pred:

                prediction = {
                    "issue": next_period,
                    "prediction": pred,
                    "reason": reason,
                    "level": simulation_level
                }

                last_prediction_issue = next_period

                text = make_prediction_message(
                    next_period,
                    pred,
                    reason,
                    simulation_level
                )

                send_new_channel_message(text)

                print(
                    "FIRST PREDICTION:",
                    next_period,
                    pred
                )

        return

    # -----------------------------------------------------
    # NEW COMPLETED RESULT
    # -----------------------------------------------------

    if completed_issue != last_completed_issue:

        print(
            "NEW RESULT:",
            completed_issue,
            completed_number,
            completed_size
        )

        # Check previous prediction
        if prediction:

            predicted_issue = prediction["issue"]

            if predicted_issue == completed_issue:

                predicted_size = prediction["prediction"]

                if predicted_size == completed_size:

                    status = "WIN"

                    win_count += 1
                    box_win_count += 1

                    # WIN => reset simulation level
                    simulation_level = 1

                    result_text = make_result_message(
                        completed_issue,
                        completed_number,
                        completed_size,
                        predicted_size,
                        status,
                        simulation_level
                    )

                    # After 10 wins create a new box/message
                    if box_win_count >= 10:

                        prediction_message_id = None
                        box_win_count = 0

                        send_new_channel_message(
                            result_text
                        )

                    else:

                        edit_channel_message(
                            result_text
                        )

                else:

                    status = "LOSS"

                    loss_count += 1

                    # Non-money simulation level progression.
                    # No stake/bet is executed.
                    if simulation_level < 7:
                        simulation_level += 1

                    result_text = make_result_message(
                        completed_issue,
                        completed_number,
                        completed_size,
                        predicted_size,
                        status,
                        simulation_level
                    )

                    edit_channel_message(
                        result_text
                    )

                print(
                    "RESULT:",
                    status,
                    "LEVEL:",
                    simulation_level
                )

        last_completed_issue = completed_issue

        prediction = None

    # -----------------------------------------------------
    # NEW NEXT PERIOD PREDICTION
    # -----------------------------------------------------

    if next_period:

        if next_period != last_prediction_issue:

            pred, reason = pattern_prediction(history)

            if pred:

                prediction = {
                    "issue": next_period,
                    "prediction": pred,
                    "reason": reason,
                    "level": simulation_level
                }

                last_prediction_issue = next_period

                text = make_prediction_message(
                    next_period,
                    pred,
                    reason,
                    simulation_level
                )

                # New prediction goes into same box/message
                edit_channel_message(text)

                print(
                    "NEW PREDICTION:",
                    next_period,
                    pred,
                    "LEVEL:",
                    simulation_level
                )

            else:

                print(
                    "WAIT:",
                    next_period,
                    reason
                )


# =========================================================
# BACKGROUND LOOP
# =========================================================

def game_loop():

    print("GAME LOOP STARTED")

    while True:

        try:

            process_new_game_state()

        except Exception as e:

            print(
                "GAME LOOP ERROR:",
                repr(e)
            )

        time.sleep(POLL_SECONDS)


# =========================================================
# TELEGRAM COMMAND LISTENER
# =========================================================

def bot_listener():

    global owner_chat_id

    last_update_id = 0

    print("TELEGRAM LISTENER STARTED")

    while True:

        try:

            url = (
                f"https://api.telegram.org/"
                f"bot{BOT_TOKEN}/getUpdates"
            )

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

                print(
                    "GET UPDATES ERROR:",
                    data
                )

                time.sleep(5)
                continue

            for update in data.get("result", []):

                last_update_id = update["update_id"]

                message = update.get("message")

                if not message:
                    continue

                chat = message.get("chat", {})

                chat_id = chat.get("id")

                text = message.get(
                    "text",
                    ""
                ).strip()

                if not chat_id:
                    continue

                # -------------------------------------------------
                # OWNER SETUP
                # -------------------------------------------------

                if owner_chat_id is None:

                    if text.startswith("/start"):

                        owner_chat_id = chat_id

                        telegram_send(
                            chat_id,
                            "✅ Owner connected.\n"
                            "VeerGame Predictor live mode."
                        )

                        print(
                            "OWNER CHAT ID SET:",
                            owner_chat_id
                        )

                    continue

                # -------------------------------------------------
                # ONLY OWNER
                # -------------------------------------------------

                if chat_id != owner_chat_id:

                    # Ignore everyone else
                    continue

                # -------------------------------------------------
                # COMMANDS
                # -------------------------------------------------

                if text.startswith("/start"):

                    telegram_send(
                        chat_id,
                        "✅ VeerGame Predictor running.\n\n"
                        f"Level: {simulation_level}/7\n"
                        f"Wins: {win_count}\n"
                        f"Losses: {loss_count}"
                    )

                elif text.startswith("/status"):

                    telegram_send(
                        chat_id,
                        "📊 BOT STATUS\n"
                        "━━━━━━━━━━━━━━\n"
                        f"Level: {simulation_level}/7\n"
                        f"Wins: {win_count}\n"
                        f"Losses: {loss_count}\n"
                        f"Current prediction: "
                        f"{prediction}"
                    )

                elif text.startswith("/history"):

                    latest_text = []

                    for item in history_cache[:15]:

                        latest_text.append(
                            f"{item['issue']} "
                            f"{item['number']} "
                            f"{item['size']}"
                        )

                    if latest_text:

                        telegram_send(
                            chat_id,
                            "📚 LAST 15 RESULTS\n\n"
                            + "\n".join(latest_text)
                        )

                    else:

                        telegram_send(
                            chat_id,
                            "History abhi available nahi hai."
                        )

                elif text.startswith("/reset"):

                    simulation_level = 1
                    win_count = 0
                    loss_count = 0
                    box_win_count = 0

                    telegram_send(
                        chat_id,
                        "♻️ Simulation stats reset.\n"
                        "Level = 1/7"
                    )

        except Exception as e:

            print(
                "BOT LISTENER ERROR:",
                repr(e)
            )

            time.sleep(5)


# =========================================================
# WEB
# =========================================================

@app.route("/")
def home():

    return (
        "VeerGame Predictor is running."
    )


@app.route("/test")
def test():

    return {
        "bot_token_present": bool(BOT_TOKEN),
        "channel_id": CHANNEL_ID,
        "history_url": HISTORY_URL,
        "current_url": CURRENT_URL,
        "level": simulation_level,
        "wins": win_count,
        "losses": loss_count,
        "prediction": prediction
    }


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    print("================================"
    print("VEERGAME PRED
