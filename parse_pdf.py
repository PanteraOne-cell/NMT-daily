#!/usr/bin/env python3
"""
parse_pdf.py
Конвертує PDF-файли НМТ у JSON-банк завдань.
Працює без Claude API — використовує PyMuPDF + regex.

Структура НМТ-PDF:
  - Питання: рядок починається з цифри і крапки ("1.", "2.", ...)
  - Варіанти: рядки з "А)", "Б)", "В)", "Г)", "Д)" або "A)", "B)" тощо
  - Файл відповідей: окремий PDF з таблицею типу "1 – А", "2 – Б"

Використання:
    python parse_pdf.py \
        --pdf pdfs/math_2025_v1.pdf \
        --answers pdfs/math_2025_answers.pdf \
        --subject math --year 2025 --variant 1

Залежності:
    pip install pymupdf
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Встановіть PyMuPDF: pip install pymupdf")
    sys.exit(1)

from subjects import SUBJECT_NAMES, detect_topic

BANK_DIR = Path(__file__).parent / "bank"

OPTION_PATTERN = re.compile(
    r'^([АBCДЕабвгдABCDE])[)\.]\s*(.+)$',
    re.IGNORECASE | re.UNICODE
)

OPTION_NORMALIZE = {
    'А': 'A', 'а': 'A',
    'Б': 'B', 'б': 'B',
    'В': 'C', 'в': 'C',
    'Г': 'D', 'г': 'D',
    'Д': 'E', 'д': 'E',
    'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'E': 'E',
}


def extract_text(pdf_path):
    doc = fitz.open(pdf_path)
    pages = [page.get_text("text") for page in doc]
    doc.close()
    return "\n".join(pages)


def parse_questions(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    questions = []
    current_q = None
    current_options = {}
    current_text_lines = []

    q_start = re.compile(r'^(\d{1,2})\.\s+(.+)$')

    for line in lines:
        q_match = q_start.match(line)
        opt_match = OPTION_PATTERN.match(line)

        if q_match:
            if current_q is not None and len(current_options) >= 4:
                questions.append({
                    "number": current_q,
                    "text": " ".join(current_text_lines).strip(),
                    "options": current_options,
                })
            current_q = int(q_match.group(1))
            current_text_lines = [q_match.group(2)]
            current_options = {}

        elif opt_match and current_q is not None:
            letter = OPTION_NORMALIZE.get(opt_match.group(1).upper(), opt_match.group(1).upper())
            current_options[letter] = opt_match.group(2).strip()

        elif current_q is not None and not current_options:
            current_text_lines.append(line)

    if current_q is not None and len(current_options) >= 4:
        questions.append({
            "number": current_q,
            "text": " ".join(current_text_lines).strip(),
            "options": current_options,
        })

    return questions


def parse_answers(answers_pdf_path):
    text = extract_text(answers_pdf_path)
    answers = {}

    patterns = [
        re.compile(r'(\d{1,2})\s*[–\-—]\s*([АБВГДабвгдABCDE])', re.UNICODE),
        re.compile(r'(\d{1,2})[\.]\s*([АБВГДабвгдABCDE])\b', re.UNICODE),
        re.compile(r'(\d{1,2})\s+([АБВГДабвгдABCDE])\s', re.UNICODE),
    ]

    for pattern in patterns:
        for m in pattern.finditer(text):
            num = int(m.group(1))
            letter = OPTION_NORMALIZE.get(m.group(2).upper(), m.group(2).upper())
            if num not in answers:
                answers[num] = letter

    return answers


def build_questions(raw_questions, answers, subject, source_info):
    prefix = subject[:4]
    result = []

    for q in raw_questions:
        num = q["number"]
        answer = answers.get(num, "?")
        topic = detect_topic(q["text"], subject)

        options = q["options"]
        for letter in ["A", "B", "C", "D", "E"]:
            options.setdefault(letter, "—")

        result.append({
            "id": f"{prefix}_{num:03d}",
            "topic": topic,
            "year": int(source_info.split()[-2]) if source_info else 2025,
            "source": source_info,
            "type": "single_choice",
            "text": q["text"],
            "options": {k: options[k] for k in ["A", "B", "C", "D", "E"]},
            "answer": answer,
            "explanation": "",
        })

    return result


def merge_with_bank(new_questions, subject):
    bank_path = BANK_DIR / f"{subject}.json"

    if bank_path.exists():
        bank = json.loads(bank_path.read_text(encoding="utf-8"))
        existing_ids = {q["id"] for q in bank["questions"]}
        existing_texts = {q["text"][:50] for q in bank["questions"]}
        unique = [
            q for q in new_questions
            if q["id"] not in existing_ids and q["text"][:50] not in existing_texts
        ]
        bank["questions"].extend(unique)
    else:
        bank = {
            "subject": subject,
            "subject_name": SUBJECT_NAMES.get(subject, subject),
            "questions": new_questions,
        }
        unique = new_questions

    bank["total_questions"] = len(bank["questions"])
    bank_path.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(unique)


def process(pdf_path, answers_path, subject, year, variant):
    source_info = f"НМТ {year}, варіант {variant}"
    print(f"Читаю: {pdf_path}")

    text = extract_text(pdf_path)
    raw_questions = parse_questions(text)
    print(f"  Знайдено питань: {len(raw_questions)}")

    answers = {}
    if answers_path:
        print(f"  Читаю відповіді: {answers_path}")
        answers = parse_answers(answers_path)
        print(f"  Знайдено відповідей: {len(answers)}")

    questions = build_questions(raw_questions, answers, subject, source_info)
    added = merge_with_bank(questions, subject)
    print(f"  Додано до банку: {added} нових завдань")
    return added


def main():
    parser = argparse.ArgumentParser(description="Парсер PDF НМТ → JSON банк (без Claude API)")
    parser.add_argument("--pdf", required=True, help="Шлях до PDF із завданнями")
    parser.add_argument("--answers", help="Шлях до PDF з відповідями (необов'язково)")
    parser.add_argument(
        "--subject", required=True,
        choices=list(SUBJECT_NAMES.keys()),
        help="Предмет: math, ukrainian, history, biology",
    )
    parser.add_argument("--year", type=int, default=2025, help="Рік НМТ")
    parser.add_argument("--variant", default="1", help="Номер варіанту")
    args = parser.parse_args()

    if not os.path.exists(args.pdf):
        print(f"Файл не знайдено: {args.pdf}")
        sys.exit(1)

    total = process(args.pdf, args.answers, args.subject, args.year, args.variant)
    print(f"\nГотово! Додано {total} завдань до банку '{args.subject}'.")


if __name__ == "__main__":
    main()
