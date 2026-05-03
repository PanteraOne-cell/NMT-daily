#!/usr/bin/env python3
"""Backfill image URLs for bank questions that lack the field.

Scans zno.osvita.ua /all/OFFSET/ pages to find images for questions
that were scraped without one. Safe to re-run: already-updated questions
are skipped.

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

from common import BASE_URL, HEADERS

DELAY = 1.5

BASE_DIR = Path(__file__).parent.parent
BANK_DIR = BASE_DIR / "bank"

ALL_SUBJECTS = ["ukrainian", "math", "history", "biology"]

SUBJECT_URL = {
    "ukrainian": "ukrainian",
    "math":      "mathematics",
    "history":   "ukraine-history",
    "biology":   "biology",
}


def extract_images_from_page(html: str) -> dict[str, str]:
    """Return {question_id → absolute_image_url} for questions with images on this page."""
    result: dict[str, str] = {}
    blocks = re.split(r'(?=<input[^>]+name="q\[out_order\]")', html)
    for block in blocks:
        if 'class="question"' not in block:
            continue
        m_id = re.search(r'name="q\[id\]"[^>]+value="(\d+)"', block)
        if not m_id:
            m_id = re.search(r'value="(\d+)"[^>]+name="q\[id\]"', block)
        if not m_id:
            continue
        qid = m_id.group(1)
        m_q = re.search(r'class="question">(.*?)(?:<div class="(?:answers|clear)")', block, re.S)
        region = m_q.group(1) if m_q else block
        m_img = re.search(r'<img[^>]+src="([^"]+)"', region)
        if m_img:
            img_url = m_img.group(1)
            if not img_url.startswith("http"):
                img_url = BASE_URL + img_url
            result[qid] = img_url
    return result


def get_page_question_ids(html: str) -> list[str]:
    """Return all question IDs on the page, in page order."""
    ids = re.findall(r'name="q\[id\]"[^>]+value="(\d+)"', html)
    if not ids:
        ids = re.findall(r'value="(\d+)"[^>]+name="q\[id\]"', html)
    return list(dict.fromkeys(ids))


def backfill_subject(subject: str) -> int:
    path = BANK_DIR / f"{subject}.json"
    if not path.exists():
        print(f"  {subject}: bank не знайдено, пропускаю")
        return 0

    bank = json.loads(path.read_text(encoding="utf-8"))
    questions = bank["questions"] if isinstance(bank, dict) else bank

    # Build lookup: numeric_id_str → index in questions list
    need_image: dict[str, int] = {}
    for i, q in enumerate(questions):
        if not q.get("image") and q.get("source_id", "").startswith("zno_"):
            numeric_id = q["source_id"].removeprefix("zno_")
            need_image[numeric_id] = i

    print(f"\n[{subject}] {len(need_image)} питань без зображення")
    if not need_image:
        return 0

    url_subject = SUBJECT_URL[subject]
    remaining = set(need_image)
    updated = 0
    offset = 15
    consecutive_no_match = 0

    while remaining:
        url = f"{BASE_URL}/{url_subject}/all/{offset}/"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=25)
            if resp.status_code == 404:
                print(f"  offset={offset}: 404, кінець сторінок")
                break
            resp.raise_for_status()
        except Exception as e:
            print(f"  offset={offset}: помилка — {e}")
            offset += 15
            time.sleep(DELAY)
            continue

        page_ids = get_page_question_ids(resp.text)
        if not page_ids:
            consecutive_no_match += 1
            if consecutive_no_match >= 3:
                print(f"  offset={offset}: 3 порожні сторінки поспіль, зупиняюсь")
                break
            offset += 15
            time.sleep(DELAY)
            continue
        consecutive_no_match = 0

        # IDs decrease as offset increases; stop once all page IDs < min remaining
        min_page_id = min(int(x) for x in page_ids)
        min_remaining = min(int(x) for x in remaining)
        if min_page_id < min_remaining and not (set(page_ids) & remaining):
            print(f"  offset={offset}: min page ID {min_page_id} < min target {min_remaining}, зупиняюсь")
            break

        images_on_page = extract_images_from_page(resp.text)
        found_on_page = set(page_ids) & remaining

        for qid in found_on_page:
            remaining.discard(qid)
            if qid in images_on_page:
                idx = need_image[qid]
                questions[idx]["image"] = images_on_page[qid]
                updated += 1

        if found_on_page:
            imgs_count = sum(1 for q in found_on_page if q in images_on_page)
            print(f"  offset={offset}: знайдено {len(found_on_page)} питань, {imgs_count} з зображенням, залишилось {len(remaining)}")
        else:
            print(f"  offset={offset}: цільових питань нема, залишилось {len(remaining)}")
            consecutive_no_match += 1
            if consecutive_no_match >= 20:
                print(f"  20 сторінок поспіль без збігів, зупиняюсь")
                break

        offset += 15
        time.sleep(DELAY)

    if updated:
        if isinstance(bank, dict):
            bank["total_questions"] = len(questions)
        path.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  -> {updated} оновлень збережено в bank/{subject}.json")

    return updated


def main() -> None:
    subjects = sys.argv[1:] if len(sys.argv) > 1 else ALL_SUBJECTS
    unknown = [s for s in subjects if s not in ALL_SUBJECTS]
    if unknown:
        print(f"Невідомі предмети: {unknown}. Доступні: {ALL_SUBJECTS}")
        sys.exit(1)

    try:
        r = requests.get(BASE_URL + "/ukrainian/all/15/", headers=HEADERS, timeout=10)
        print(f"[TEST] {BASE_URL}: HTTP {r.status_code}")
    except Exception as e:
        print(f"[TEST] {BASE_URL} недоступний: {e}")

    total = 0
    for subject in subjects:
        total += backfill_subject(subject)
    print(f"\nВсього оновлено: {total} питань")


if __name__ == "__main__":
    main()
