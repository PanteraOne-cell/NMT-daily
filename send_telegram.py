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


def send_to(chat_id: str, text: str, q: dict):
    opts_lines = "\n".join(f"{k}. {v}" for k, v in q["options"].items())
    full_text = f"{text}\n\n{opts_lines}"

    image_path = q.get("image")
    first_msg_id: int | None = None
    use_text_only = True

    if image_path:
        img_file = Path(image_path)
        if not img_file.exists():
            print(f"WARNING: image not found: {image_path} — sending text only")
        else:
            use_text_only = False
            # caption limit is 1024 chars
            caption = full_text if len(full_text) <= 1024 else text
            extra = opts_lines if len(full_text) > 1024 else None

            with open(img_file, "rb") as fh:
                resp = _post(
                    "sendPhoto",
                    data={"chat_id": chat_id, "caption": caption},
                    files={"photo": fh},
                )
            first_msg_id = resp.json()["result"]["message_id"]

            if extra:
                _post("sendMessage", json={"chat_id": chat_id, "text": extra})

    if use_text_only:
        resp = _post("sendMessage", json={"chat_id": chat_id, "text": full_text})
        first_msg_id = resp.json()["result"]["message_id"]

    # spoiler with correct answer, replying to the first sent message
    _post("sendMessage", json={
        "chat_id": chat_id,
        "text": f"✅ Правильна відповідь: ||{q['answer']}||",
        "reply_parameters": {"message_id": first_msg_id},
        "parse_mode": "MarkdownV2",
    })


def main():
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC] Starting...")
    if not CHAT_IDS:
        print("ERROR: CHAT_IDS not set in .env")
        return

    subject = random.choice(list(SUBJECTS.keys()))
    q = load_question(subject)

    label = SUBJECTS.get(subject, subject)
    text = f"{label}\n\n{q['text']}"

    for i, chat_id in enumerate(CHAT_IDS):
        if i > 0:
            time.sleep(1)
        send_to(chat_id, text, q)
        print(f"OK [{chat_id}]: {subject}")


if __name__ == "__main__":
    main()
