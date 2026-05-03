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

NEEDS_IMAGE_KW = [
    "на рисунку", "на фото", "позначено буквою",
    "зображено", "на діаграмі", "на карті", "на схемі",
]


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

    def is_valid(q: dict) -> bool:
        if q.get("answer") not in q.get("options", {}):
            return False
        text_lower = q.get("text", "").lower()
        needs_image = any(kw in text_lower for kw in NEEDS_IMAGE_KW)
        has_image = bool(q.get("image_url") or q.get("image"))
        return not (needs_image and not has_image)

    valid = [q for q in questions if is_valid(q)]
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
    question = truncate(f"{label}\n\n{clean(q['text'])}", 255)
    options = [{"text": f"{k}. {clean(v)}"[:100]} for k, v in q["options"].items()]
    keys = list(q["options"].keys())
    correct_option_id = keys.index(q["answer"])
    _post("sendPoll", json={
        "chat_id": chat_id,
        "question": question,
        "options": options,
        "type": "quiz",
        "correct_option_id": correct_option_id,
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
