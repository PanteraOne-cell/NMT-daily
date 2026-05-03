#!/usr/bin/env python3
"""Expand bank/{subject}.json to --target questions each.

Usage:
    python scripts/backfill.py --subject all --target 500
    python scripts/backfill.py --subject math --target 500
"""
import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scraper"))
sys.path.insert(0, str(ROOT))

from parse_question import parse_all_questions  # noqa: E402
from subjects import SUBJECT_NAMES, detect_topic  # noqa: E402
from common import BASE_URL, HEADERS  # noqa: E402
BANK_DIR = ROOT / "bank"
STEP = 15

# bank filename → URL slug
SLUG = {
    "ukrainian": "ukrainian",
    "math":      "mathematics",
    "history":   "ukraine-history",
    "biology":   "biology",
}
ALL_SUBJECTS = list(SLUG.keys())


# ── helpers ──────────────────────────────────────────────────────────────────

def load_bank(subject: str) -> dict:
    path = BANK_DIR / f"{subject}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def save_bank(bank: dict, subject: str) -> None:
    BANK_DIR.mkdir(exist_ok=True)
    bank["total_questions"] = len(bank["questions"])
    path = BANK_DIR / f"{subject}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def existing_source_ids(bank: dict) -> set[str]:
    return {
        q["source_id"].removeprefix("zno_")
        for q in bank["questions"]
        if q.get("source_id", "").startswith("zno_")
    }


def first_uncovered_offset(done_ids: set[str]) -> int:
    """Estimate the first page offset that likely contains unseen questions.

    Questions on a page at offset N have roughly the same numeric IDs as N.
    Starting just below the minimum known ID avoids re-scanning all already-
    fetched pages from the top.
    """
    if not done_ids:
        return STEP
    min_id = min(int(x) for x in done_ids if x.isdigit())
    # go two pages back from the minimum to avoid off-by-one on page boundaries
    return max(STEP, (min_id // STEP - 2) * STEP)


def fetch_page(slug: str, offset: int) -> str | None:
    url = f"{BASE_URL}/{slug}/all/{offset}/"
    delay = 2.0
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=25)
            if resp.status_code == 404:
                return None
            if resp.status_code == 429:
                print(f"    [429] rate-limit, backing off {delay:.0f}s …")
                time.sleep(delay)
                delay *= 2
                continue
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            print(f"    [attempt {attempt+1}] {exc}")
            time.sleep(delay)
            delay *= 2
    return None


def build_entry(raw: dict, subject: str, slug: str) -> dict | None:
    qid = raw.get("id")
    if not qid:
        return None

    choices = raw.get("choices", [])
    if len(choices) < 2:
        return None

    options: dict[str, str] = {ch["label"]: ch["text"] for ch in choices}
    for letter in ["A", "B", "C", "D", "E"]:
        options.setdefault(letter, "—")

    correct = raw.get("correct")
    if not correct or correct not in options:
        return None

    entry: dict = {
        "id":          f"{subject[:4]}_zno_{qid}",
        "source_id":   f"zno_{qid}",
        "topic":       detect_topic(raw.get("question", ""), subject),
        "year":        None,
        "source":      f"zno.osvita.ua/{slug}/{qid}",
        "type":        "single_choice",
        "text":        raw.get("question", ""),
        "options":     {k: options[k] for k in ["A", "B", "C", "D", "E"]},
        "answer":      correct,
        "explanation": "",
    }

    img = raw.get("image_url")
    if img:
        entry["image"] = img if img.startswith("http") else BASE_URL + img

    return entry


# ── per-subject logic ─────────────────────────────────────────────────────────

def backfill_subject(subject: str, target: int) -> dict:
    slug = SLUG[subject]
    bank = load_bank(subject)
    questions: list[dict] = bank["questions"]
    before = len(questions)
    imgs_before = sum(1 for q in questions if q.get("image"))

    if before >= target:
        print(f"  {subject}: {before} >= {target}, нічого не потрібно")
        return {"subject": subject, "before": before, "after": before,
                "new": 0, "with_image": imgs_before}

    done_ids = existing_source_ids(bank)
    need = target - before
    added = 0
    offset = first_uncovered_offset(done_ids)
    consecutive_empty = 0

    print(f"  {subject}: {before} → потрібно ще {need}")
    while added < need:
        print(f"    {slug}/all/{offset}/ … ", end="", flush=True)
        html = fetch_page(slug, offset)

        if html is None:
            print("404 / помилка, зупиняюсь")
            break

        parsed = parse_all_questions(html)
        if not parsed:
            consecutive_empty += 1
            print(f"0 питань ({consecutive_empty} порожніх поспіль)")
            if consecutive_empty >= 3:
                print("    3 порожні сторінки, зупиняюсь")
                break
            offset += STEP
            time.sleep(random.uniform(0.5, 1.0))
            continue
        consecutive_empty = 0

        new_on_page = 0
        for raw in parsed:
            qid = raw.get("id")
            if not qid or qid in done_ids:
                continue
            entry = build_entry(raw, subject, slug)
            if not entry:
                continue
            questions.append(entry)
            done_ids.add(qid)
            added += 1
            new_on_page += 1
            if added >= need:
                break

        print(f"+{new_on_page} (нових разом: {added}/{need})")
        offset += STEP
        time.sleep(random.uniform(0.5, 1.0))

    if added:
        save_bank(bank, subject)

    after = len(questions)
    with_image = sum(1 for q in questions if q.get("image"))
    return {"subject": subject, "before": before, "after": after,
            "new": added, "with_image": with_image}


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    # Force UTF-8 output on Windows so Cyrillic/arrows don't crash
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Expand NMT question banks")
    parser.add_argument("--subject", choices=ALL_SUBJECTS + ["all"], default="all")
    parser.add_argument("--target", type=int, default=500)
    args = parser.parse_args()

    subjects = ALL_SUBJECTS if args.subject == "all" else [args.subject]

    # connectivity check
    try:
        r = requests.get(f"{BASE_URL}/ukrainian/all/15/", headers=HEADERS, timeout=10)
        print(f"[connectivity] {BASE_URL} → HTTP {r.status_code}\n")
    except Exception as exc:
        print(f"[connectivity] {BASE_URL} недоступний: {exc}")
        sys.exit(1)

    results = []
    for subj in subjects:
        print(f"\n[{subj}]")
        results.append(backfill_subject(subj, args.target))

    # summary
    print("\n" + "─" * 62)
    print(f"{'subject':<12} {'before':>7} {'after':>7} {'new':>6} {'with_img':>9}")
    print("─" * 62)
    for r in results:
        flag = "" if r["after"] >= args.target else "  ⚠ нижче target"
        print(f"{r['subject']:<12} {r['before']:>7} {r['after']:>7} "
              f"{r['new']:>6} {r['with_image']:>9}{flag}")
    print("─" * 62)


if __name__ == "__main__":
    main()
