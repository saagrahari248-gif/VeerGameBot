import os
import random
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from flask import Flask

app = Flask(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

LEVEL = 1
HISTORY = []


def send_telegram(message):
    print("TOKEN present:", bool(TOKEN))
    print("CHANNEL_ID present:", bool(CHANNEL_ID))
    print("CHANNEL_ID value:", CHANNEL_ID)

    if not TOKEN or not CHANNEL_ID:
        print("ERROR: BOT_TOKEN or CHANNEL_ID missing")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    try:
        response = requests.post(
            url,
            json={
                "chat_id": CHANNEL_ID,
                "text": message
                
