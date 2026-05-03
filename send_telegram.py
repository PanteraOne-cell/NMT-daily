import html
import json
import random
import os
import re
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

SENT_PATH   = Path("data/sent.json")   # relative to CWD (repo root)
SENT_WINDOW = 200


def clean(text: str) -> str:
    text = html.unescape(str(text))
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    return text


def truncate(text: str, limit: int) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def strip_latex(text: str) -> str:
    # LaTeX inline math uses \( ... \) where \( is TWO chars: backslash + paren.
    # In regex:  \\\(  matches literal \(  ;  \\\)  matches literal \)
    text = re.sub(r'\\\(\\frac\{([^}]+)\}\{([^}]+)\}\\\)', r'\1/\2', text)
    text = re.sub(r'\\\((\d+)\\circ\\\)',                   r'\1°',   text)
    text = re.sub(r'\\\(\\sqrt\{([^}]+)\}\\\)',             r'√\1',   text)
    text = text.replace('\\(\\pi\\)', 'π')
    text = re.sub(r'\\\(([^)]+)\^\{?2\}?\\\)',              r'\1²',   text)
    text = re.sub(r'\\\(([^)]+)\^\{?3\}?\\\)',              r'\1³',   text)
    text = re.sub(r'\\\(|\\\)',                             '',       text)
    return text


def _escape_md(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!\\])', r'\\\1', str(text))


# ── sent-question tracking ────────────────────────────────────────────────────

def _load_sent() -> set[str]:
    if SENT_PATH.exists():
        return set(json.loads(SENT_PATH.read_text(encoding="utf-8")).get("sent", []))
    return set()


def _save_sent(q_id: str) -> None:
    SENT_PATH.parent.mkdir(exist_ok=True)
    data = json.loads(SENT_PATH.read_text(encoding="utf-8")) if SENT_PATH.exists() else {"sent": []}
    sent_list: list[str] = data["sent"]
    if q_id not in sent_list:
        sent_list.append(q_id)
    data["sent"] = sent_list[-SENT_WINDOW:]
    SENT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── core helpers ──────────────────────────────────────────────────────────────

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

    recently_sent = _load_sent()
    unsent = [q for q in valid if q.get("id") not in recently_sent]
    return random.choice(unsent if unsent else valid)


def _post(endpoint: str, **kwargs) -> requests.Response:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{endpoint}"
    delay = 2.0
    for attempt in range(3):
        try:
            resp = requests.post(url, timeout=15, **kwargs)
        except requests.RequestException as exc:
            if attempt == 2:
                raise
            print(f"  [{endpoint}] network error (attempt {attempt + 1}): {exc}")
            time.sleep(delay)
            delay *= 2
            continue
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", delay))
            print(f"  [{endpoint}] rate-limited, retry in {retry_after}s")
            time.sleep(retry_after)
            continue
        if not resp.ok:
            print(f"Telegram error {endpoint}: {resp.status_code} {resp.text}")
        resp.raise_for_status()
        return resp
    resp.raise_for_status()  # unreachable, satisfies type checkers
    return resp


def send_to(chat_id: str, subject: str, q: dict):
    label = SUBJECTS.get(subject, subject)
    image_url = q.get("image")
    question_text = _escape_md(strip_latex(clean(q["text"])))

    # Step 1 / 2 — context message (photo or text)
    if image_url:
        caption = f"{_escape_md(label)}\n\n❓ {question_text}"
        resp = _post("sendPhoto", json={
            "chat_id":    chat_id,
            "photo":      image_url,
            "caption":    caption,
            "parse_mode": "MarkdownV2",
        })
    else:
        text = f"{_escape_md(label)}\n\n❓ {question_text}"
        resp = _post("sendMessage", json={
            "chat_id":    chat_id,
            "text":       text,
            "parse_mode": "MarkdownV2",
        })
    reply_message_id = resp.json()["result"]["message_id"]

    # Step 3 — quiz poll (filter out "—" placeholders, recompute correct index)
    pairs = [(k, v) for k, v in q["options"].items() if v != "—"]
    options = [{"text": strip_latex(clean(v))[:100]} for _, v in pairs]
    correct_option_id = [k for k, _ in pairs].index(q["answer"])
    _post("sendPoll", json={
        "chat_id":             chat_id,
        "question":            "Оберіть правильну відповідь:",
        "options":             options,
        "type":                "quiz",
        "correct_option_id":   correct_option_id,
        "is_anonymous":        True,
        "reply_to_message_id": reply_message_id,
    })

    _save_sent(q.get("id", ""))


def main():
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC] Starting...")
    if not CHAT_IDS:
        print("ERROR: CHAT_IDS not set in .env")
        return

    subjects = list(SUBJECTS.keys())
    random.shuffle(subjects)

    for i, chat_id in enumerate(CHAT_IDS):
        if i > 0:
            time.sleep(1)
        subject = subjects[i % len(subjects)]
        q = load_question(subject)
        send_to(chat_id, subject, q)
        print(f"OK [{chat_id}]: {subject}")


if __name__ == "__main__":
    main()
