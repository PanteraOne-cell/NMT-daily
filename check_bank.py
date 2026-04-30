#!/usr/bin/env python3
"""
check_bank.py
Перевіряє стан банку завдань і надсилає сповіщення в Telegram
якщо для якоїсь теми залишилось мало невідправлених завдань.

Запуск:
    python check_bank.py          # перевірка + Telegram
    python check_bank.py --report # тільки звіт у консоль
"""

import json
import os
import sys
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

from subjects import SUBJECT_NAMES, SUBJECT_EMOJIS

KYIV_TZ = timezone(timedelta(hours=3))

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config" / "schedule.json"
STATS_PATH  = BASE_DIR / "stats" / "progress.json"
BANK_DIR    = BASE_DIR / "bank"

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_IDS = [
    os.environ.get("TELEGRAM_CHAT_ID_1", ""),
    os.environ.get("TELEGRAM_CHAT_ID_2", ""),
]

WARN_THRESHOLD = 5

PDF_LINKS = {
    "math":      "https://osvita.ua/test/answers/95542/",
    "ukrainian": "https://osvita.ua/test/answers/95541/",
    "history":   "https://osvita.ua/test/answers/95543/",
    "biology":   "https://osvita.ua/test/answers/95545/",
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def send_message(token, chat_id, text):
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"Помилка: {e}")
        return False


def get_bank_stats(subject, stats):
    bank_path = BANK_DIR / f"{subject}.json"
    if not bank_path.exists():
        return {"total": 0, "sent": 0, "remaining": 0, "topics": {}}

    bank = load_json(bank_path)
    all_questions = bank.get("questions", [])
    sent_ids = set(stats["subjects"].get(subject, {}).get("sent", []))

    total = len(all_questions)
    sent = len([q for q in all_questions if q["id"] in sent_ids])
    remaining = total - sent

    topics = {}
    for q in all_questions:
        topic = q.get("topic", "Інше")
        if topic not in topics:
            topics[topic] = {"total": 0, "remaining": 0}
        topics[topic]["total"] += 1
        if q["id"] not in sent_ids:
            topics[topic]["remaining"] += 1

    return {"total": total, "sent": sent, "remaining": remaining, "topics": topics}


def build_report(stats):
    lines = []
    warnings = []
    now = datetime.now(KYIV_TZ).strftime("%d.%m.%Y %H:%M")

    lines.append(f"🗃 <b>Стан банку завдань</b>  {now}")
    lines.append("")

    for subject in SUBJECT_NAMES:
        s = get_bank_stats(subject, stats)
        emoji = SUBJECT_EMOJIS[subject]
        name = SUBJECT_NAMES[subject]

        lines.append(f"{emoji} <b>{name}</b>")
        lines.append(f"   Всього: {s['total']} | Відправлено: {s['sent']} | Залишилось: {s['remaining']}")

        low_topics = [
            (topic, d["remaining"])
            for topic, d in s["topics"].items()
            if d["remaining"] < WARN_THRESHOLD
        ]

        if low_topics:
            low_str = ", ".join(f"{t} ({r})" for t, r in sorted(low_topics, key=lambda x: x[1]))
            lines.append(f"   ⚠️ Мало: {low_str}")
            warnings.append((subject, low_topics))
        lines.append("")

    return "\n".join(lines), warnings


def build_warning_message(warnings):
    lines = ["⚠️ <b>NMT-Daily: поповнити банк</b>", ""]
    for subject, low_topics in warnings:
        emoji = SUBJECT_EMOJIS[subject]
        name = SUBJECT_NAMES[subject]
        link = PDF_LINKS.get(subject, "")
        lines.append(f"{emoji} <b>{name}</b>")
        for topic, remaining in sorted(low_topics, key=lambda x: x[1]):
            lines.append(f"   • {topic}: {remaining} залишилось")
        if link:
            lines.append(f"   📥 PDF: {link}")
        lines.append("")
    lines.append("Завантаж PDF → поклади в <code>pdfs/</code> → запусти <b>Parse PDF to Bank</b>")
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Перевірка стану банку НМТ")
    parser.add_argument("--report", action="store_true", help="Тільки звіт у консоль")
    args = parser.parse_args()

    if not STATS_PATH.exists():
        print("stats/progress.json не знайдено.")
        sys.exit(1)

    stats = load_json(STATS_PATH)

    report, warnings = build_report(stats)
    print(report)

    if args.report:
        return

    if not warnings:
        print("Банк у нормі — сповіщення не потрібне.")
        return

    warning_msg = build_warning_message(warnings)

    for chat_id in CHAT_IDS:
        if not chat_id:
            continue
        if send_message(BOT_TOKEN, chat_id, warning_msg):
            print(f"Сповіщення надіслано до {chat_id}")


if __name__ == "__main__":
    main()
