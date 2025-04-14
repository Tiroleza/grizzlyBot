import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
UPDATE_URL = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
AUTHORIZED_FILE = "authorized_ids.json"

def get_updates():
    response = requests.get(UPDATE_URL)
    return response.json().get("result", [])

def load_authorized_ids():
    if os.path.exists(AUTHORIZED_FILE):
        with open(AUTHORIZED_FILE, "r") as f:
            return json.load(f)
    return []

def save_authorized_ids(ids):
    with open(AUTHORIZED_FILE, "w") as f:
        json.dump(ids, f)

def process_updates():
    updates = get_updates()
    authorized = load_authorized_ids()

    for update in updates:
        msg = update.get("message")
        if not msg:
            continue

        chat_id = msg["chat"]["id"]
        text = msg.get("text", "").strip().lower()

        if text == "/robbery4":
            if chat_id not in authorized:
                authorized.append(chat_id)
                save_authorized_ids(authorized)
                print(f"✅ Novo autorizado: {chat_id}")
                requests.post(
                    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                    json={"chat_id": chat_id, "text": "🔓 Acesso autorizado com sucesso!"}
                )
            else:
                print(f"ℹ️ Já autorizado: {chat_id}")
        else:
            print(f"📨 {chat_id} enviou: {text}")

if __name__ == "__main__":
    process_updates()