import json
import pytest
from pathlib import Path


def test_check_subject_missing_file(tmp_path, monkeypatch):
    import check_bank
    monkeypatch.setattr(check_bank, "BANK_DIR", tmp_path)
    result = check_bank.check_subject("math")
    assert result == {"total": 0, "valid": 0, "with_image": 0}


def test_check_subject_counts_valid(tmp_path, monkeypatch):
    import check_bank
    monkeypatch.setattr(check_bank, "BANK_DIR", tmp_path)

    questions = [
        {"id": "q1", "options": {"A": "x"}, "answer": "A"},
        {"id": "q2", "options": {"A": "x"}, "answer": "B"},  # invalid: B not in options
        {"id": "q3", "options": {"A": "x", "B": "y"}, "answer": "B", "image": "https://img.com/1.png"},
    ]
    (tmp_path / "math.json").write_text(
        json.dumps({"questions": questions}), encoding="utf-8"
    )
    result = check_bank.check_subject("math")
    assert result["total"] == 3
    assert result["valid"] == 2
    assert result["with_image"] == 1


def test_check_subject_no_images(tmp_path, monkeypatch):
    import check_bank
    monkeypatch.setattr(check_bank, "BANK_DIR", tmp_path)

    questions = [
        {"id": "q1", "options": {"A": "x"}, "answer": "A"},
        {"id": "q2", "options": {"A": "x", "B": "y"}, "answer": "A"},
    ]
    (tmp_path / "math.json").write_text(
        json.dumps({"questions": questions}), encoding="utf-8"
    )
    result = check_bank.check_subject("math")
    assert result["with_image"] == 0
    assert result["valid"] == 2


def test_check_subject_flat_json_list(tmp_path, monkeypatch):
    """Bank stored as bare list (not wrapped in dict) must still be counted."""
    import check_bank
    monkeypatch.setattr(check_bank, "BANK_DIR", tmp_path)

    questions = [{"id": "q1", "options": {"A": "x"}, "answer": "A"}]
    (tmp_path / "math.json").write_text(json.dumps(questions), encoding="utf-8")

    result = check_bank.check_subject("math")
    assert result["total"] == 1
    assert result["valid"] == 1


def test_check_subject_all_invalid(tmp_path, monkeypatch):
    import check_bank
    monkeypatch.setattr(check_bank, "BANK_DIR", tmp_path)

    questions = [
        {"id": "q1", "options": {"A": "x"}, "answer": "Z"},  # Z not in options
        {"id": "q2", "options": {}, "answer": "A"},           # no options at all
    ]
    (tmp_path / "math.json").write_text(
        json.dumps({"questions": questions}), encoding="utf-8"
    )
    result = check_bank.check_subject("math")
    assert result["total"] == 2
    assert result["valid"] == 0
    assert result["with_image"] == 0


def test_check_subject_empty_bank(tmp_path, monkeypatch):
    import check_bank
    monkeypatch.setattr(check_bank, "BANK_DIR", tmp_path)

    (tmp_path / "biology.json").write_text(
        json.dumps({"questions": []}), encoding="utf-8"
    )
    result = check_bank.check_subject("biology")
    assert result == {"total": 0, "valid": 0, "with_image": 0}


def test_main_outputs_all_subjects(tmp_path, monkeypatch, capsys):
    """main() must print a row for every subject."""
    import check_bank
    monkeypatch.setattr(check_bank, "BANK_DIR", tmp_path)

    for subj in ["math", "ukrainian", "history", "biology"]:
        qs = [{"id": "q1", "options": {"A": "x"}, "answer": "A"}]
        (tmp_path / f"{subj}.json").write_text(
            json.dumps({"questions": qs}), encoding="utf-8"
        )

    check_bank.main()
    out = capsys.readouterr().out
    assert "Математика" in out
    assert "Українська мова" in out
    assert "Історія України" in out
    assert "Біологія" in out
