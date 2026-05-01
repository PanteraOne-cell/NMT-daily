import html
import json
import random
import os
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_IDS = [cid.strip() for cid in os.getenv("CHAT_IDS", "").split(",") if cid.strip()]

SUBJECTS = {
    "math":      "📐 Математика",
    "ukrainian": "📝 Українська мова",
    "history":   "📜 Історія України",
    "biology":   "🧬 Біологія",
}


def clean(text: str) -> str:
    text = html.unescape(str(text))
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    return text


def truncate(text: str, limit: int) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def load_question(subject: str) -> dict:
    path = Path(f"bank/{subject}.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    questions = data["questions"] if isinstance(data, dict) else data
    valid = [q for q in questions if q.get("answer") in q.get("options", {})]
    if not valid:
        raise ValueError(f"No valid questions in {subject}")
    return random.choice(valid)


def _post(endpoint: str, **kwargs) -> requests.Response:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{endpoint}"
    resp = requests.post(url, **kwargs)
    if not resp.ok:
        print(f"Telegram error {endpoint}: {resp.status_code} {resp.text}")
    resp.raise_for_status()
    return resp


def send_to(chat_id: str, subject: str, q: dict):
    label = SUBJECTS.get(subject, subject)
    question_text = f"{label}\n\n{clean(q['text'])}"

    image_val = q.get("image")
    image_url = image_val if (image_val and image_val.startswith("http")) else None
    image_path = Path(__file__).parent / image_val if (image_val and not image_url) else None

    if image_url:
        print(f"[INFO] image URL: {image_url}")
    elif image_path:
        print(f"[INFO] image field: {image_val}")
        print(f"[INFO] resolved path: {image_path.resolve()}")
        print(f"[INFO] file exists: {image_path.exists()}")

    first_msg_id: int
    if image_url:
        resp = _post("sendPhoto", json={
            "chat_id": chat_id, "photo": image_url, "caption": question_text,
        })
        print(f"[INFO] sendPhoto (URL): {resp.status_code} ok={resp.json().get('ok')}")
        first_msg_id = resp.json()["result"]["message_id"]
    elif image_path and image_path.exists():
        with open(image_path, "rb") as photo:
            resp = _post(
                "sendPhoto",
                data={"chat_id": chat_id, "caption": question_text},
                files={"photo": photo},
            )
        print(f"[INFO] sendPhoto (file): {resp.status_code} ok={resp.json().get('ok')}")
        first_msg_id = resp.json()["result"]["message_id"]
    else:
        if image_val:
            print(f"[WARNING] image not available: {image_val}")
        resp = _post("sendMessage", json={"chat_id": chat_id, "text": question_text})
        first_msg_id = resp.json()["result"]["message_id"]

    options = [f"{k}. {clean(v)}"[:100] for k, v in q["options"].items()]
    keys = list(q["options"].keys())
    correct_option_id = keys.index(q["answer"])

    _post("sendPoll", json={
        "chat_id": chat_id,
        "question": "Оберіть правильну відповідь:",
        "options": options,
        "type": "quiz",
        "correct_option_id": correct_option_id,
        "reply_to_message_id": first_msg_id,
        "is_anonymous": True,
    })


def main():
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC] Starting...")
    if not CHAT_IDS:
        print("ERROR: CHAT_IDS not set in .env")
        return

    subject = random.choice(list(SUBJECTS.keys()))
    q = load_question(subject)

    for i, chat_id in enumerate(CHAT_IDS):
        if i > 0:
            time.sleep(1)
        send_to(chat_id, subject, q)
        print(f"OK [{chat_id}]: {subject}")


if __name__ == "__main__":
    main()
