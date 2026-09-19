import os
import requests
import threading

# ==============================================================================
# TELEGRAM CONFIGURATION
# 1. Create a bot via @BotFather to get your TELEGRAM_BOT_TOKEN.
# 2. Get your numeric ID via @userinfobot to get your TELEGRAM_CHAT_ID.
# 3. Important: Send /start to your bot in Telegram first!
# ==============================================================================
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"

def _send_worker(message, photo_path=None):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("[TELEGRAM] Missing Bot Token. Skipping notification.")
        return

    try:
        if photo_path and os.path.exists(photo_path):
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            with open(photo_path, "rb") as photo:
                payload = {
                    "chat_id": TELEGRAM_CHAT_ID,
                    "caption": message,
                    "parse_mode": "Markdown"
                }
                files = {"photo": photo}
                res = requests.post(url, data=payload, files=files, timeout=8)
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            }
            res = requests.post(url, json=payload, timeout=8)

        if res.status_code == 200:
            print("[TELEGRAM ALERT] Sent successfully.")
        else:
            print(f"[TELEGRAM ERROR] API Response: {res.text}")
    except Exception as e:
        print(f"[TELEGRAM ERROR] Dispatch failed: {e}")

def send_telegram_alert(message, photo_path=None):
    """Dispatches Telegram notifications asynchronously without blocking the video stream."""
    threading.Thread(target=_send_worker, args=(message, photo_path), daemon=True).start()