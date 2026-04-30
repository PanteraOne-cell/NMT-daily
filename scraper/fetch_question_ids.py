#!/usr/bin/env python3
import json
import re
import time
from pathlib import Path
import requests

# Ключі мають точно збігатись з SUBJECT_MAP у build_database.py
SUBJECTS = {
    "ukrainian":   "https://zno.osvita.ua/ukrainian/all/",
    "mathematics": "https://zno.osvita.ua/mathematics/all/",
    "history":     "https://zno.osvita.ua/ukraine-history/all/",
    "biology":     "https://zno.osvita.ua/biology/all/",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; nmt-daily-bot/1.0)"}
DATA_DIR = Path(__file__).parent.parent / "data"
STEP = 15


def get_ids_for_subject(subject: str, base_url: str) -> list[int]:
    ids = set()
    offset = 15

    while True:
        url = f"{base_url}{offset}/"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 404:
                break
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  [{subject}] offset={offset} помилка: {e}")
            break

        found = re.findall(r'name="q\[id\]"[^>]+value="(\d+)"', resp.text)
        found += re.findall(r'value="(\d+)"[^>]+name="q\[id\]"', resp.text)

        if not found:
            break

        new_ids = {int(i) for i in found}
        before = len(ids)
        ids |= new_ids

        print(f"  [{subject}] offset={offset}: +{len(new_ids)} → всього {len(ids)}")

        if len(ids) == before:
            break

        offset += STEP
        time.sleep(1)

    return sorted(ids, reverse=True)


def main():
    DATA_DIR.mkdir(exist_ok=True)
    all_ids: dict[str, list[int]] = {}

    for subject, base_url in SUBJECTS.items():
        print(f"\n{subject}:")
        all_ids[subject] = get_ids_for_subject(subject, base_url)
        print(f"  Разом: {len(all_ids[subject])} питань")
        time.sleep(2)

    out = DATA_DIR / "question_ids.json"
    out.write_text(json.dumps(all_ids, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nЗбережено → {out}")


if __name__ == "__main__":
    main()
