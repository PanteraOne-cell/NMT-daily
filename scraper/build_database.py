#!/usr/bin/env python3
import argparse
import json
import time
from pathlib import Path
import sys
import requests

sys.path.insert(0, str(Path(__file__).parent))        # parse_question
sys.path.insert(0, str(Path(__file__).parent.parent)) # subjects
from parse_question import parse_all_questions
from subjects import SUBJECT_NAMES, detect_topic

BASE_DIR = Path(__file__).parent.parent
BANK_DIR = BASE_DIR / "bank"
DATA_DIR = BASE_DIR / "data"
IDS_FILE = DATA_DIR / "question_ids.json"

BASE_URL = "https://zno.osvita.ua"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; nmt-daily-bot/1.0; educational use)",
    "Accept-Language": "uk-UA,uk;q=0.9",
}

# Ключі мають точно збігатись з SUBJECTS у fetch_question_ids.py
SUBJECT_MAP = {
    "ukrainian":   {"bank": "ukrainian", "url": "ukrainian"},
    "mathematics": {"bank": "math",      "url": "mathematics"},
    "history":     {"bank": "history",   "url": "ukraine-history"},
    "biology":     {"bank": "biology",   "url": "biology"},
}

DELAY   = 1.5
MAX_NEW = 50


def load_bank(bank_subject: str) -> dict:
    path = BANK_DIR / f"{bank_subject}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "subject":      bank_subject,
        "subject_name": SUBJECT_NAMES.get(bank_subject, bank_subject),
        "questions":    [],
    }


def save_bank(bank: dict, bank_subject: str):
    BANK_DIR.mkdir(exist_ok=True)
    bank["total_questions"] = len(bank["questions"])
    path = BANK_DIR / f"{bank_subject}.json"
    path.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")


def existing_source_ids(bank: dict) -> set[str]:
    return {
        q.get("source_id", "")
        for q in bank["questions"]
        if q.get("source_id", "").startswith("zno_")
    }


def fetch_page(url_subject: str, offset: int) -> list[dict]:
    url = f"{BASE_URL}/{url_subject}/all/{offset}/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"    ⚠️ {e}")
        return []
    return parse_all_questions(resp.text)


def to_bank_entry(raw: dict, bank_subject: str, url_subject: str, qid: int) -> dict:
    prefix = bank_subject[:4]

    options: dict[str, str] = {}
    for ch in raw.get("choices", []):
        options[ch["label"]] = ch["text"]
    for letter in ["A", "B", "C", "D", "E"]:
        options.setdefault(letter, "—")

    return {
        "id":          f"{prefix}_zno_{qid}",
        "source_id":   f"zno_{qid}",
        "topic":       detect_topic(raw.get("question", ""), bank_subject),
        "year":        None,
        "source":      f"zno.osvita.ua/{url_subject}/{qid}",
        "type":        "single_choice",
        "text":        raw.get("question", ""),
        "options":     {k: options[k] for k in ["A", "B", "C", "D", "E"]},
        "answer":      raw.get("correct") or "?",
        "explanation": raw.get("explanation", ""),
    }


def process_subject(subject_key: str, limit: int) -> int:
    cfg = SUBJECT_MAP[subject_key]
    bank_subject = cfg["bank"]
    url_subject  = cfg["url"]

    bank = load_bank(bank_subject)
    done_ids = existing_source_ids(bank)

    added  = 0
    offset = 15
    step   = 15

    while added < limit:
        print(f"  → {url_subject}/all/{offset}/ ... ", end="", flush=True)
        questions = fetch_page(url_subject, offset)

        if not questions:
            print("стоп")
            break

        new = 0
        for q in questions:
            if added >= limit:
                break
            qid = q.get("id")
            if not qid:
                continue
            source_id = f"zno_{qid}"
            if source_id in done_ids:
                continue
            bank["questions"].append(
                to_bank_entry(q, bank_subject, url_subject, int(qid))
            )
            done_ids.add(source_id)
            added += 1
            new += 1

        print(f"+{new} (всього {added})")
        offset += step
        time.sleep(DELAY)

    if added:
        save_bank(bank, bank_subject)
        print(f"  Збережено {added} нових → bank/{bank_subject}.json")

    return added


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", choices=list(SUBJECT_MAP))
    parser.add_argument("--limit", type=int, default=MAX_NEW)
    args = parser.parse_args()

    subjects = [args.subject] if args.subject else list(SUBJECT_MAP)
    total = 0

    for subject_key in subjects:
        print(f"\n[{subject_key}]")
        total += process_subject(subject_key, args.limit)

    print(f"\nГотово. Всього додано: {total} питань.")


if __name__ == "__main__":
    main()
