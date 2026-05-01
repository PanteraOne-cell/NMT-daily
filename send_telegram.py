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


def escape_md(text: str) -> str:
    specials = set('\\_*[]()~`>#+-=|{}.!')
    return "".join(("\\" + ch if ch in specials else ch) for ch in str(text))


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


def format_message(subject: str, q: dict) -> str:
    label = SUBJECTS.get(subject, subject)
    lines = [escape_md(label), "", escape_md(clean(q["text"])), ""]
    for k, v in q["options"].items():
        lines.append(escape_md(f"{k}. {clean(v)}"))
    lines.append("\n📌 [@nmt\\_daily\\_ua](https://t.me/nmt_daily_ua)")
    return "\n".join(lines)


def _safe_callback_data(answer_key: str, answer_text: str) -> str:
    data = f"✅ {answer_key}. {clean(answer_text)}"
    encoded = data.encode("utf-8")
    if len(encoded) > 64:
        data = encoded[:64].decode("utf-8", errors="ignore")
    return data


def send_to(chat_id: str, text: str, answer_key: str, answer_full: str):
    reply_markup = {
        "inline_keyboard": [[{
            "text": "💡 Показати відповідь",
            "callback_data": _safe_callback_data(answer_key, answer_full),
        }]]
    }
    _post("sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "MarkdownV2",
        "reply_markup": reply_markup,
    })


def process_callbacks():
    resp = _post("getUpdates", json={"timeout": 5, "allowed_updates": ["callback_query"]})
    updates = resp.json().get("result", [])
    if not updates:
        return
    last_update_id = updates[-1]["update_id"]
    for update in updates:
        cq = update.get("callback_query")
        if cq:
            _post("answerCallbackQuery", json={
                "callback_query_id": cq["id"],
                "text": cq["data"],
                "show_alert": True,
            })
    _post("getUpdates", json={"offset": last_update_id + 1, "timeout": 1})


def main():
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC] Starting...")
    if not CHAT_IDS:
        print("ERROR: CHAT_IDS not set in .env")
        return

    process_callbacks()

    subject = random.choice(list(SUBJECTS.keys()))
    q = load_question(subject)
    text = format_message(subject, q)
    answer_full = q["options"].get(q["answer"], q["answer"])

    for i, chat_id in enumerate(CHAT_IDS):
        if i > 0:
            time.sleep(1)
        send_to(chat_id, text, q["answer"], answer_full)
        print(f"OK [{chat_id}]: {subject}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "callbacks":
        process_callbacks()
    else:
        main()
