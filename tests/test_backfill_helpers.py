from scripts.backfill import (
    existing_source_ids,
    first_uncovered_offset,
    build_entry,
    STEP,
)


# ── existing_source_ids ───────────────────────────────────────────────────────

def test_existing_source_ids_extracts_numeric():
    bank = {
        "questions": [
            {"id": "math_zno_12345", "source_id": "zno_12345"},
            {"id": "math_zno_67890", "source_id": "zno_67890"},
        ]
    }
    assert existing_source_ids(bank) == {"12345", "67890"}


def test_existing_source_ids_skips_non_zno():
    bank = {
        "questions": [
            {"id": "math_001", "source_id": "pdf_001"},
            {"id": "math_zno_111", "source_id": "zno_111"},
        ]
    }
    ids = existing_source_ids(bank)
    assert ids == {"111"}


def test_existing_source_ids_empty_bank():
    assert existing_source_ids({"questions": []}) == set()


def test_existing_source_ids_missing_source_id():
    bank = {"questions": [{"id": "math_001"}]}  # no source_id key
    assert existing_source_ids(bank) == set()


# ── first_uncovered_offset ────────────────────────────────────────────────────

def test_first_uncovered_offset_empty_returns_step():
    assert first_uncovered_offset(set()) == STEP


def test_first_uncovered_offset_computes_correctly():
    done_ids = {"1000", "1015", "1030"}
    result = first_uncovered_offset(done_ids)
    # min_id = 1000; (1000 // 15 - 2) * 15 = 64 * 15 = 960
    assert result == 960


def test_first_uncovered_offset_clamps_to_step():
    done_ids = {"5", "10"}
    assert first_uncovered_offset(done_ids) >= STEP


def test_first_uncovered_offset_large_ids():
    done_ids = {"50000"}
    result = first_uncovered_offset(done_ids)
    # (50000 // 15 - 2) * 15 = (3333 - 2) * 15 = 3331 * 15 = 49965
    assert result == 49965


# ── build_entry ───────────────────────────────────────────────────────────────

def _raw(extra=None):
    base = {
        "id": "12345",
        "question": "Яке значення 2+2?",
        "choices": [
            {"label": "A", "text": "3"},
            {"label": "B", "text": "4"},
            {"label": "C", "text": "5"},
        ],
        "correct": "B",
    }
    if extra:
        base.update(extra)
    return base


def test_build_entry_basic():
    entry = build_entry(_raw(), "math", "mathematics")
    assert entry is not None
    assert entry["id"] == "math_zno_12345"
    assert entry["source_id"] == "zno_12345"
    assert entry["answer"] == "B"
    assert entry["options"]["B"] == "4"
    assert entry["type"] == "single_choice"
    assert entry["source"] == "zno.osvita.ua/mathematics/12345"


def test_build_entry_missing_id():
    raw = _raw()
    raw["id"] = None
    assert build_entry(raw, "math", "mathematics") is None


def test_build_entry_empty_id():
    raw = _raw()
    raw["id"] = ""
    assert build_entry(raw, "math", "mathematics") is None


def test_build_entry_too_few_choices():
    raw = _raw()
    raw["choices"] = [{"label": "A", "text": "x"}]
    assert build_entry(raw, "math", "mathematics") is None


def test_build_entry_invalid_answer_not_in_options():
    raw = _raw()
    raw["correct"] = "Z"
    assert build_entry(raw, "math", "mathematics") is None


def test_build_entry_missing_correct():
    raw = _raw()
    raw["correct"] = None
    assert build_entry(raw, "math", "mathematics") is None


def test_build_entry_fills_missing_options_with_dash():
    entry = build_entry(_raw(), "math", "mathematics")
    assert entry is not None
    assert entry["options"]["D"] == "—"
    assert entry["options"]["E"] == "—"


def test_build_entry_with_relative_image_url():
    raw = _raw({"image_url": "/doc/images/bio_123.png"})
    entry = build_entry(raw, "biology", "biology")
    assert entry is not None
    assert "image" in entry
    assert entry["image"].startswith("http")
    assert "bio_123.png" in entry["image"]


def test_build_entry_with_absolute_image_url():
    raw = _raw({"image_url": "https://zno.osvita.ua/doc/images/math_999.png"})
    entry = build_entry(raw, "math", "mathematics")
    assert entry is not None
    assert entry["image"] == "https://zno.osvita.ua/doc/images/math_999.png"


def test_build_entry_no_image_key_when_missing():
    entry = build_entry(_raw(), "math", "mathematics")
    assert "image" not in entry


def test_build_entry_subject_prefix_truncated_to_4():
    entry = build_entry(_raw(), "ukrainian", "ukrainian")
    assert entry["id"].startswith("ukra_zno_")


def test_build_entry_all_option_keys_present():
    entry = build_entry(_raw(), "math", "mathematics")
    assert set(entry["options"].keys()) == {"A", "B", "C", "D", "E"}
