import re

LABEL_NORM = {"a": "A", "b": "B", "c": "C", "d": "D", "e": "E"}
CYR_NORM   = {"А": "A", "Б": "B", "В": "C", "Г": "D", "Д": "E"}

def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)

def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def parse_all_questions(html: str) -> list[dict]:
    results = []

    # Знаходимо блоки: input[hidden] + div.question + div.answers
    # Шаблон: один блок питання від <input name="q[out_order]" до наступного такого або кінця
    blocks = re.split(r'(?=<input[^>]+name="q\[out_order\]")', html)

    for block in blocks:
        if 'class="question"' not in block:
            continue

        # ID питання
        m_id = re.search(r'name="q\[id\]"[^>]+value="(\d+)"', block)
        if not m_id:
            m_id = re.search(r'value="(\d+)"[^>]+name="q\[id\]"', block)
        qid = m_id.group(1) if m_id else None

        # Правильна відповідь
        m_res = re.search(r'name="result"[^>]+value="([a-eа-дАБВГД])"', block)
        if not m_res:
            m_res = re.search(r'value="([a-eа-дАБВГД])"[^>]+name="result"', block)
        correct_raw = m_res.group(1) if m_res else None
        correct = CYR_NORM.get(correct_raw, LABEL_NORM.get((correct_raw or "").lower()))

        # Текст питання
        m_q = re.search(r'class="question">(.*?)</div>\s*<div class="clear"', block, re.S)
        if not m_q:
            m_q = re.search(r'class="question">(.*?)<div class="answers"', block, re.S)
        question_text = _clean(_strip_tags(m_q.group(1))) if m_q else ""

        # Варіанти відповідей
        answer_blocks = re.findall(r'class="answer">(.*?)</div>\s*(?=<div class="answer"|</div>)', block, re.S)
        choices = []
        labels = ["A", "B", "C", "D", "E"]
        for i, ab in enumerate(answer_blocks):
            if i >= 5:
                break
            # Мітка з span.marker
            m_marker = re.search(r'class="marker">([^<]+)<', ab)
            if m_marker:
                raw = m_marker.group(1).strip()
                label = CYR_NORM.get(raw, raw.upper())
            else:
                label = labels[i]
            text = _clean(_strip_tags(ab))
            # Прибираємо мітку з початку тексту
            text = re.sub(r"^[А-ДA-Ea-e][.\s]\s*", "", text)
            if text:
                choices.append({"label": label, "text": text})

        if question_text and len(choices) >= 2:
            results.append({
                "id":          qid,
                "question":    question_text,
                "choices":     choices,
                "correct":     correct,
                "explanation": "",
            })

    return results


def parse_question(html: str) -> dict | None:
    results = parse_all_questions(html)
    return results[0] if results else None