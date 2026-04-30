import html, json, random, re, sys
from pathlib import Path

_MD_SPECIAL = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")
def escape_md(text): return _MD_SPECIAL.sub(r"\\\1", str(text))
def clean(text): return html.unescape(str(text))

SUBJECTS = {
    "math":      "Математика",
    "ukrainian": "Українська мова",
    "history":   "Історія України",
    "biology":   "Біологія",
}
ENTITY_MARKERS = ["&laquo;", "&raquo;", "&nbsp;", "&ndash;", "&quot;", "&amp;"]

print("=" * 60)
all_ok = True

for subject, label in SUBJECTS.items():
    path = Path(f"bank/{subject}.json")
    if not path.exists():
        print(f"\n[{subject}] SKIP — файл відсутній")
        continue

    data = json.loads(path.read_text(encoding="utf-8"))
    questions = data["questions"] if isinstance(data, dict) else data
    total = len(questions)
    valid = [q for q in questions if q.get("answer") in q.get("options", {})]
    bad_count = total - len(valid)

    q = random.choice(valid)
    raw_text = q["text"]
    cleaned_text = clean(raw_text)
    has_entities_raw = any(e in raw_text for e in ENTITY_MARKERS)
    has_entities_after = any(e in cleaned_text for e in ENTITY_MARKERS)
    opts_count = len(q["options"])
    answer = q["answer"]
    answer_valid = answer in q["options"]

    status = "OK" if (not has_entities_after and answer_valid) else "FAIL"
    if status == "FAIL":
        all_ok = False

    print(f"\n[{subject}] {status}")
    print(f"  Bank: total={total}, valid={len(valid)}, bad(?)={bad_count}")
    print(f"  HTML entities raw/after clean: {has_entities_raw} / {has_entities_after}")
    print(f"  Options count: {opts_count}  |  Answer '{answer}' in options: {answer_valid}")
    print(f"  Text (60 ch): {cleaned_text[:60]}")
    for k, v in q["options"].items():
        marker = " <-- correct" if k == answer else ""
        print(f"    {k}: {clean(v)[:55]}{marker}")
    print(f"  escape_md sample: {escape_md(cleaned_text[:50])}")

print("\n" + "=" * 60)
print("Result: ALL OK" if all_ok else "Result: FAILURES FOUND")
sys.exit(0 if all_ok else 1)
