#!/usr/bin/env python3
"""Backfill image URLs for bank questions that lack the field.

Fetches each question's individual page from zno.osvita.ua and extracts
the img src from the question block. Safe to re-run: already-updated
questions are skipped.

Usage:
    python scraper/backfill_images.py                  # all subjects
    python scraper/backfill_images.py history biology  # specific subjects
"""

import json
import re
import sys
import time
from pathlib import Path

import requests

BASE_URL = "https://zno.osvita.ua"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; nmt-daily-bot/1.0; educational use)",
    "Accept-Language": "uk-UA,uk;q=0.9",
}
DELAY = 1.2

BASE_DIR = Path(__file__).parent.parent
BANK_DIR = BASE_DIR / "bank"

ALL_SUBJECTS = ["ukrainian", "math", "history", "biology"]


def extract_image_url(html: str) -> str | None:
    m = re.search(r'class="question">(.*?)(?:<div class="(?:answers|clear)")', html, re.S)
    region = m.group(1) if m else html
    m_img = re.search(r'<img[^>]+src="([^"]+)"', region)
    return m_img.group(1) if m_img else None


def fetch_page(source: str) -> str | None:
    url = f"https://{source}/" if not source.startswith("http") else source
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        print(f"    ⚠️  {e}")
        return None


def backfill_subject(subject: str) -> int:
    path = BANK_DIR / f"{subject}.json"
    if not path.exists():
        print(f"  {subject}: bank не знайдено, пропускаю")
        return 0

    bank = json.loads(path.read_text(encoding="utf-8"))
    questions = bank["questions"] if isinstance(bank, dict) else bank

    to_check = [
        (i, q) for i, q in enumerate(questions)
        if not q.get("image") and q.get("source")
    ]

    print(f"\n[{subject}] {len(to_check)} питань без зображення")
    if not to_check:
        return 0

    updated = 0
    for n, (idx, q) in enumerate(to_check, 1):
        html = fetch_page(q["source"])
        time.sleep(DELAY)

        if not html:
            print(f"  {n}/{len(to_check)} {q['source_id']} — не вдалося завантажити")
            continue

        img_url = extract_image_url(html)
        if img_url:
            if not img_url.startswith("http"):
                img_url = BASE_URL + img_url
            questions[idx]["image"] = img_url
            updated += 1
            print(f"  {n}/{len(to_check)} {q['source_id']} ✓")
        else:
            print(f"  {n}/{len(to_check)} {q['source_id']} — без зображення")

    if updated:
        if isinstance(bank, dict):
            bank["total_questions"] = len(questions)
        path.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  → {updated} оновлень збережено в bank/{subject}.json")

    return updated


def main() -> None:
    subjects = sys.argv[1:] if len(sys.argv) > 1 else ALL_SUBJECTS
    unknown = [s for s in subjects if s not in ALL_SUBJECTS]
    if unknown:
        print(f"Невідомі предмети: {unknown}. Доступні: {ALL_SUBJECTS}")
        sys.exit(1)

    total = 0
    for subject in subjects:
        total += backfill_subject(subject)
    print(f"\nВсього оновлено: {total} питань")


if __name__ == "__main__":
    main()
