# NMT Daily — Claude context

## Project purpose

Telegram bot that sends NMT/ZNO exam questions daily. One question per subject (math, ukrainian, history, biology) per hour to configured chats. Runs entirely on GitHub Actions; no server needed.

## Architecture

```
send_telegram.py          ← main entry point, runs on every workflow trigger
subjects.py               ← canonical subject registry (names, emojis, topic keywords)
check_bank.py             ← bank health report (informational, always exit 0)
parse_pdf.py              ← offline PDF → JSON bank converter (requires pymupdf)

scraper/
  common.py               ← shared BASE_URL + HEADERS for all HTTP scrapers
  parse_question.py       ← HTML parser for zno.osvita.ua question blocks
  backfill_images.py      ← crawls zno.osvita.ua to fill missing image URLs

scripts/
  backfill.py             ← expands bank/{subject}.json to --target count
  trigger_workflow.py     ← dispatches GitHub Actions workflow via API

bank/{subject}.json       ← question banks (math, ukrainian, history, biology)
data/sent.json            ← rolling window of last 200 sent question IDs
```

## Data schema

### `bank/{subject}.json`
```json
{
  "subject": "math",
  "subject_name": "Математика",
  "questions": [{
    "id": "math_zno_37461",
    "source_id": "zno_37461",
    "topic": "Тригонометрія",
    "year": null,
    "source": "zno.osvita.ua/mathematics/37461",
    "type": "single_choice",
    "text": "...",
    "options": {"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."},
    "answer": "A",
    "explanation": "",
    "image": "https://..."
  }],
  "total_questions": 500
}
```

Key invariants:
- `answer` must be a key in `options` (otherwise question is invalid)
- `options` always has A–E keys; missing values filled with `"—"`
- `image` field is only present when a question has a visual
- `id` format: `{subject[:4]}_zno_{numeric_id}` for scraped; `{prefix}_{num:03d}` for PDF-parsed
- `source_id` format: `zno_{numeric_id}` for scraped questions

### `data/sent.json`
```json
{"sent": ["math_zno_12345", "biol_zno_67890", ...]}
```
Rolling list capped at 200 entries. `load_question()` prefers questions NOT in this list.

## Subject registry (`subjects.py`)

Single source of truth. **Always import from here**, never duplicate.

```python
SUBJECT_NAMES   # {"math": "Математика", ...}
SUBJECT_EMOJIS  # {"math": "📐", "ukrainian": "📝", "history": "📜", "biology": "🧬"}
TOPIC_KEYWORDS  # keyword → topic name, used by detect_topic()
detect_topic(text, subject) → str  # returns topic name or "Загальне"
```

`detect_topic` uses first-match on keyword substrings (lowercase). Order matters — more specific topics should come after general ones that share keywords.

## Question filtering (`send_telegram.py`)

`load_question(subject)` rejects:
1. `answer` not in `options`
2. Any option value is an image URL (bot can't display them)
3. Text contains image-reference keywords (`NEEDS_IMAGE_KW`) AND `image` field is absent

Image-reference keywords: `"на рисунку"`, `"на фото"`, `"позначено буквою"`, `"зображено"`, `"зображення"`, `"на діаграмі"`, `"на карті"`, `"на схемі"`.

## Send flow

Per trigger: 4 questions (one per subject, random order) × N chats.

For each question:
1. `sendPhoto` (with caption) if `image` field exists, else `sendMessage`
2. `sendPoll` (quiz type, anonymous, correct answer marked, reply_to step 1)
3. `_save_sent()` — appends ID to `data/sent.json`

## GitHub Actions workflows

| Workflow | Trigger | Purpose |
|---|---|---|
| `send_daily.yml` | `0 * * * *` + dispatch | Sends daily questions |
| `build_db.yml` | `0 3 * * 1` + dispatch | Scrapes new questions |
| `check_bank.yml` | `0 6 * * 6` + dispatch | Reports bank stats |
| `backfill_images.yml` | dispatch only | Fills missing image URLs |
| `parse_pdf.yml` | dispatch only | Imports PDF exam file |

The `send_daily.yml` is also triggered externally via cron-job.org → GitHub dispatch API (see `docs/setup_cronjob.md`).

Required GitHub Secrets: `BOT_TOKEN`, `CHAT_IDS` (comma-separated).

## Running tests

```bash
pip install pytest pyyaml
pytest                  # runs all 85 tests
pytest tests/test_send_telegram.py -v   # specific file
```

All tests are offline (no network, no Telegram API). `conftest.py` adds project root and `scraper/` to `sys.path`.

## Adding a new subject

1. Add to `SUBJECT_NAMES`, `SUBJECT_EMOJIS`, `TOPIC_KEYWORDS` in `subjects.py`
2. Add URL slug to `SLUG` in `scripts/backfill.py` and `SUBJECT_URL` in `scraper/backfill_images.py`
3. Create `bank/{subject}.json` with `{"subject": "...", "subject_name": "...", "questions": []}`
4. `SUBJECTS` list in `send_telegram.py` is derived automatically from `SUBJECT_NAMES`

## Common operations

```bash
# Check bank health
python check_bank.py

# Run quality check (standalone script, not pytest)
python _test_quality.py

# Expand bank to 600 questions
python scripts/backfill.py --subject all --target 600

# Backfill missing images
python scraper/backfill_images.py biology

# Parse PDF exam file
python parse_pdf.py --pdf exam.pdf --answers answers.pdf --subject math --year 2025 --variant 1
```

## Known design decisions

- **Double `html.unescape`** in `clean()`: intentional — some source data has double-encoded HTML entities (e.g., `&amp;lt;` → `&lt;` → `<`)
- **`SENT_WINDOW = 200`**: rolling window prevents repeat questions while keeping file size constant
- **Atomic writes** (`os.replace` on `.tmp`): prevents partial bank corruption if process is killed mid-write
- **`detect_topic` order sensitivity**: first-match design means more general keywords (e.g., "функці") will shadow specific ones if they appear earlier in the list. When adding topics, put more specific topics first or ensure their keywords are unambiguous
- **`parse_question.py` answer regex** only matches `[a-e]` lowercase Latin + Cyrillic — uppercase Latin (A,B,C,D,E) as answer values in HTML are not supported

## Improvement ideas

- **CI test step**: add `pytest` to `send_daily.yml` so tests run on every push
- **Geography subject**: `SUBJECT_URL` already has a placeholder gap — can add with slug `geography`
- **`detect_topic` ordering**: "Функції та графіки" keyword `"функці"` catches too many unrelated questions; consider moving it later in the list or tightening keyword to `"графік функц"`
- **Retry on `_save_sent`**: currently no retry if file write fails (race condition with git push)
- **Structured logging**: replace `print()` with `logging` for better CI log filtering
- **`_test_quality.py`**: standalone script at root; could be converted to `scripts/quality_check.py` for clarity
