#!/usr/bin/env python3
"""Звіт про стан банку завдань.

Підраховує валідні питання (answer ∈ options) у bank/*.json і виводить таблицю.
Завжди exit(0) — суто інформаційний звіт.

Запуск: python check_bank.py
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from subjects import SUBJECT_NAMES, SUBJECT_EMOJIS

KYIV_TZ = timezone(timedelta(hours=3))
BANK_DIR = Path(__file__).parent / "bank"


def check_subject(subject: str) -> dict:
    path = BANK_DIR / f"{subject}.json"
    if not path.exists():
        return {"total": 0, "valid": 0, "with_image": 0}
    data = json.loads(path.read_text(encoding="utf-8"))
    questions = data["questions"] if isinstance(data, dict) else data
    valid = [q for q in questions if q.get("answer") in q.get("options", {})]
    with_image = sum(1 for q in valid if q.get("image"))
    return {"total": len(questions), "valid": len(valid), "with_image": with_image}


def main():
    now = datetime.now(KYIV_TZ).strftime("%d.%m.%Y %H:%M")
    print(f"Стан банку НМТ — {now}\n")
    print(f"{'Предмет':<22} {'Всього':>7} {'Валідних':>9} {'З фото':>7}")
    print("-" * 48)
    for subject, name in SUBJECT_NAMES.items():
        emoji = SUBJECT_EMOJIS.get(subject, "")
        s = check_subject(subject)
        print(f"{emoji} {name:<19} {s['total']:>7} {s['valid']:>9} {s['with_image']:>7}")
    print()


if __name__ == "__main__":
    main()
