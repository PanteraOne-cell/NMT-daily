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


def escape_md(text: str) -> str:
    specials = set('\\_*[]()~`>#+-=|{}.!')
    return "".join(("\\" + ch if ch in specials else ch) for ch in str(text))


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


def format_message(subject: str, q: dict) -> str:
    label = SUBJECTS.get(subject, subject)
    lines = [f"*{escape_md(label)}*", "", f"❓ {escape_md(clean(q['text']))}", ""]
    for k, v in q["options"].items():
        lines.append(escape_md(f"{k}. {clean(v)}"))
    lines.append("\n📌 [@nmt\\_daily\\_ua](https://t.me/nmt_daily_ua)")
    return "\n".join(lines)


def send_to(chat_id: str, text: str, q: dict):
    image_url = q.get("image_url") or q.get("image")

    if image_url:
        if len(text) <= 1024:
            resp = _post("sendPhoto", json={
                "chat_id": chat_id,
                "photo": image_url,
                "caption": text,
                "parse_mode": "MarkdownV2",
            })
            first_id = resp.json()["result"]["message_id"]
        else:
            photo = _post("sendPhoto", json={
                "chat_id": chat_id,
                "photo": image_url,
            })
            photo_id = photo.json()["result"]["message_id"]
            msg = _post("sendMessage", json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "MarkdownV2",
                "reply_parameters": {"message_id": photo_id},
            })
            first_id = msg.json()["result"]["message_id"]
    else:
        resp = _post("sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "MarkdownV2",
        })
        first_id = resp.json()["result"]["message_id"]

    answer_text = q["options"].get(q["answer"], q["answer"])
    spoiler = f"||✅ Правильна відповідь: {escape_md(clean(answer_text))}||"
    _post("sendMessage", json={
        "chat_id": chat_id,
        "text": spoiler,
        "parse_mode": "MarkdownV2",
        "reply_parameters": {"message_id": first_id},
    })


def main():
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC] Starting...")
    if not CHAT_IDS:
        print("ERROR: CHAT_IDS not set in .env")
        return

    subject = random.choice(list(SUBJECTS.keys()))
    q = load_question(subject)
    text = format_message(subject, q)

    for i, chat_id in enumerate(CHAT_IDS):
        if i > 0:
            time.sleep(1)
        send_to(chat_id, text, q)
        print(f"OK [{chat_id}]: {subject}")


if __name__ == "__main__":
    main()
