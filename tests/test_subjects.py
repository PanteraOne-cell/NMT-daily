import pytest
from subjects import detect_topic, SUBJECT_NAMES, SUBJECT_EMOJIS, TOPIC_KEYWORDS


def test_all_subjects_have_names():
    assert set(SUBJECT_NAMES) == {"math", "ukrainian", "history", "biology"}


def test_all_subjects_have_emojis():
    assert set(SUBJECT_EMOJIS) == {"math", "ukrainian", "history", "biology"}


def test_topic_keywords_cover_all_subjects():
    assert set(TOPIC_KEYWORDS) == {"math", "ukrainian", "history", "biology"}


def test_topic_keywords_nonempty():
    for subject, topics in TOPIC_KEYWORDS.items():
        assert topics, f"No topics defined for {subject}"
        for kws, name in topics:
            assert kws, f"Empty keyword list for topic {name!r} in {subject}"
            assert name, f"Empty topic name in {subject}"


# ── Math ──────────────────────────────────────────────────────────────────────

def test_detect_topic_math_equations():
    assert detect_topic("Розв'яжіть рівняння x + 3 = 0", "math") == "Рівняння і нерівності"


def test_detect_topic_math_trig():
    assert detect_topic("Обчисліть значення sin 30° + cos 60°", "math") == "Тригонометрія"


def test_detect_topic_math_integral():
    assert detect_topic("Обчисліть визначений інтеграл функції", "math") == "Інтеграл"


def test_detect_topic_math_derivative():
    assert detect_topic("Знайдіть похідну функції y = x²", "math") == "Похідна"


def test_detect_topic_math_functions_graph():
    assert detect_topic("Побудуйте графік функції y = x²", "math") == "Функції та графіки"


def test_detect_topic_math_logarithm():
    assert detect_topic("Обчисліть логарифм числа 1000 за основою 10", "math") == "Логарифми"


def test_detect_topic_math_stereometry():
    # "радіус" matches "Планіметрія — кола" first; use "циліндр" which is unambiguous
    assert detect_topic("Знайдіть об'єм циліндра висотою 10 см", "math") == "Стереометрія"


def test_detect_topic_math_fallback():
    assert detect_topic("Невідоме математичне питання xyz", "math") == "Загальне"


# ── Ukrainian ─────────────────────────────────────────────────────────────────

def test_detect_topic_ukrainian_phonetics():
    assert detect_topic("Визначте кількість звуків у слові «школа»", "ukrainian") == "Фонетика і графіка"


def test_detect_topic_ukrainian_orthography():
    assert detect_topic("Виберіть правильне написання слова", "ukrainian") == "Орфографія"


def test_detect_topic_ukrainian_verb():
    assert detect_topic("Визначте дієслово у реченні", "ukrainian") == "Морфологія — дієслово"


def test_detect_topic_ukrainian_punctuation():
    # Need literal "кома" (nom.) and no earlier-matching keywords
    assert detect_topic("Кома між однорідними членами речення", "ukrainian") == "Пунктуація"


# ── History ───────────────────────────────────────────────────────────────────

def test_detect_topic_history_kyiv_rus():
    assert detect_topic("Охарактеризуйте правління Київської Русі", "history") == "Київська Русь"


def test_detect_topic_history_holodomor():
    assert detect_topic("Голодомор 1932–1933 років в Україні", "history") == "Голодомор і репресії"


def test_detect_topic_history_maidan():
    # "революці" keyword matches "Українська революція 1917–1921" first; avoid it
    assert detect_topic("Протести на Євромайдані у 2014 році", "history") == "Євромайдан"


def test_detect_topic_history_independence():
    assert detect_topic("Акт проголошення незалежності 1991 року", "history") == "Розпад СРСР і незалежність"


# ── Biology ───────────────────────────────────────────────────────────────────

def test_detect_topic_biology_genetics():
    assert detect_topic("Визначте генотип організму за законами Менделя", "biology") == "Генетика"


def test_detect_topic_biology_cell():
    assert detect_topic("Яка функція мітохондрій у клітині?", "biology") == "Будова клітини"


def test_detect_topic_biology_evolution():
    assert detect_topic("Природний відбір як рушійна сила еволюції за Дарвіним", "biology") == "Еволюція"


def test_detect_topic_biology_fallback():
    assert detect_topic("Питання без ключових слів xyz", "biology") == "Загальне"


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_detect_topic_unknown_subject():
    assert detect_topic("Будь-яке питання", "physics") == "Загальне"


def test_detect_topic_case_insensitive():
    # Avoid "ФУНКЦІЇ" which matches "Функції та графіки" first in topic order
    assert detect_topic("ТРИГОНОМЕТРІЯ І SIN COS", "math") == "Тригонометрія"


def test_detect_topic_empty_text():
    assert detect_topic("", "math") == "Загальне"
    assert detect_topic("", "biology") == "Загальне"
