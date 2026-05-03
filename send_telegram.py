import html
import json
import logging
import random
import os
import re
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

from subjects import SUBJECT_NAMES, SUBJECT_EMOJIS

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_IDS = [cid.strip() for cid in os.getenv("CHAT_IDS", "").split(",") if cid.strip()]

SUBJECTS = list(SUBJECT_NAMES.keys())

NEEDS_IMAGE_KW = [
    "на рисунку", "на фото", "позначено буквою",
    "зображено", "зображення", "на діаграмі", "на карті", "на схемі",
]

SENT_PATH   = Path("data/sent.json")
SENT_WINDOW = 200


def clean(text: str) -> str:
    # Double unescape: some source data has double-encoded HTML entities
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

_IMAGE_OPT_PAT = re.compile(r'^https?://|^/doc/images', re.IGNORECASE)


def _has_image_options(q: dict) -> bool:
    """True when answer options are image URLs, not displayable text."""
    return any(_IMAGE_OPT_PAT.match(str(v)) for v in q.get("options", {}).values())


def load_question(subject: str) -> dict:
    path = Path(f"bank/{subject}.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    questions = data["questions"] if isinstance(data, dict) else data

    def is_valid(q: dict) -> bool:
        if q.get("answer") not in q.get("options", {}):
            return False
        if _has_image_options(q):
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
            log.warning("[%s] network error (attempt %d): %s", endpoint, attempt + 1, exc)
            time.sleep(delay)
            delay *= 2
            continue
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", delay))
            log.warning("[%s] rate-limited, retry in %ds", endpoint, retry_after)
            time.sleep(retry_after)
            continue
        if not resp.ok:
            log.error("Telegram error %s: %s %s", endpoint, resp.status_code, resp.text)
        resp.raise_for_status()
        return resp
    resp.raise_for_status()  # unreachable, satisfies type checkers
    return resp


def send_to(chat_id: str, subject: str, q: dict):
    emoji = SUBJECT_EMOJIS.get(subject, "")
    name = SUBJECT_NAMES.get(subject, subject)
    label = f"{emoji} {name}"
    image_url = q.get("image")
    question_text = _escape_md(strip_latex(clean(q["text"])))

    # Step 1 — context message (photo or plain text)
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

    # Step 2 — quiz poll (filter "—" placeholders, recompute correct index)
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
    log.info("Starting...")
    if not CHAT_IDS:
        log.error("CHAT_IDS not set in .env")
        return

    subjects = list(SUBJECTS)
    random.shuffle(subjects)

    for subject in subjects:
        q = load_question(subject)
        for i, chat_id in enumerate(CHAT_IDS):
            if i > 0:
                time.sleep(1)
            send_to(chat_id, subject, q)
            log.info("OK [%s]: %s", chat_id, subject)
        time.sleep(2)


if __name__ == "__main__":
    main()
