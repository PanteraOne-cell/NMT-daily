import json
import random
import os
import time
import requests
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


def send_to(
    chat_id: str,
    question: str,
    options: list[str],
    correct_option_id: int,
    explanation: str,
):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPoll"
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "question": question,
        "options": options,
        "type": "quiz",
        "correct_option_id": correct_option_id,
        "explanation": explanation,
        "is_anonymous": True,
    })
    if not resp.ok:
        print(f"Telegram error [{chat_id}]: {resp.status_code} {resp.text}")
    resp.raise_for_status()


def main():
    if not CHAT_IDS:
        print("ERROR: CHAT_IDS not set in .env")
        return

    subject = random.choice(list(SUBJECTS.keys()))
    q = load_question(subject)

    label = SUBJECTS.get(subject, subject)
    question = truncate(f"{label}\n\n{q['text']}", 300)

    opts_items = list(q["options"].items())
    options = [truncate(f"{key}. {val}", 100) for key, val in opts_items]
    correct_option_id = next(
        i for i, (key, _) in enumerate(opts_items) if key == q["answer"]
    )
    explanation = truncate(f"✅ Правильна відповідь: {q['answer']}", 200)

    for i, chat_id in enumerate(CHAT_IDS):
        if i > 0:
            time.sleep(1)
        send_to(chat_id, question, options, correct_option_id, explanation)
        print(f"OK [{chat_id}]: {subject}")


if __name__ == "__main__":
    main()
