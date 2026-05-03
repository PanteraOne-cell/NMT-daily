from parse_question import parse_all_questions, parse_question


SINGLE_BLOCK = """
<input name="q[out_order]" value="1" />
<input name="q[id]" value="12345" type="hidden" />
<input name="result" value="b" type="hidden" />
<div class="question">
  Яке значення має вираз 2 + 2?
  <div class="clear"></div>
</div>
<div class="answers">
  <div class="answer"><span class="marker">А</span> 3</div>
  <div class="answer"><span class="marker">Б</span> 4</div>
  <div class="answer"><span class="marker">В</span> 5</div>
  <div class="answer"><span class="marker">Г</span> 6</div>
</div>
"""

WITH_IMAGE = """
<input name="q[out_order]" value="1" />
<input name="q[id]" value="99999" type="hidden" />
<input name="result" value="A" type="hidden" />
<div class="question">
  На рисунку зображено схему.
  <img src="/doc/images/bio_123.png" alt="schema" />
  <div class="clear"></div>
</div>
<div class="answers">
  <div class="answer"><span class="marker">А</span> Так</div>
  <div class="answer"><span class="marker">Б</span> Ні</div>
  <div class="answer"><span class="marker">В</span> Можливо</div>
  <div class="answer"><span class="marker">Г</span> Невідомо</div>
</div>
"""

LATIN_ANSWER = """
<input name="q[out_order]" value="1" />
<input name="q[id]" value="55555" type="hidden" />
<input name="result" value="c" type="hidden" />
<div class="question">Яке питання? <div class="clear"></div></div>
<div class="answers">
  <div class="answer"><span class="marker">А</span> Варіант 1</div>
  <div class="answer"><span class="marker">Б</span> Варіант 2</div>
  <div class="answer"><span class="marker">В</span> Варіант 3</div>
  <div class="answer"><span class="marker">Г</span> Варіант 4</div>
</div>
"""


def test_parse_basic_question():
    results = parse_all_questions(SINGLE_BLOCK)
    assert len(results) == 1
    q = results[0]
    assert q["id"] == "12345"
    assert q["correct"] == "B"
    assert "2 + 2" in q["question"]
    assert len(q["choices"]) == 4


def test_parse_correct_cyrillic_normalization():
    results = parse_all_questions(SINGLE_BLOCK)
    assert results[0]["correct"] == "B"  # Б → B


def test_parse_correct_latin_lowercase_normalization():
    results = parse_all_questions(LATIN_ANSWER)
    assert len(results) == 1
    assert results[0]["correct"] == "C"  # "c" → "C"


def test_parse_with_image():
    results = parse_all_questions(WITH_IMAGE)
    assert len(results) == 1
    q = results[0]
    assert "image_url" in q
    assert "bio_123.png" in q["image_url"]


def test_parse_two_blocks():
    html = SINGLE_BLOCK + WITH_IMAGE
    results = parse_all_questions(html)
    assert len(results) == 2
    ids = {r["id"] for r in results}
    assert ids == {"12345", "99999"}


def test_parse_empty_html():
    assert parse_all_questions("") == []


def test_parse_html_without_questions():
    assert parse_all_questions("<html><body>no questions</body></html>") == []


def test_parse_question_returns_first():
    result = parse_question(SINGLE_BLOCK)
    assert result is not None
    assert result["id"] == "12345"


def test_parse_question_empty_returns_none():
    assert parse_question("") is None


def test_parse_question_without_image_has_no_image_key():
    results = parse_all_questions(SINGLE_BLOCK)
    assert "image_url" not in results[0]


def test_parse_choices_have_label_and_text():
    results = parse_all_questions(SINGLE_BLOCK)
    choices = results[0]["choices"]
    for ch in choices:
        assert "label" in ch
        assert "text" in ch
        assert ch["label"] in {"A", "B", "C", "D", "E"}
        assert ch["text"]


def test_parse_skips_block_with_fewer_than_2_choices():
    minimal = """
    <input name="q[out_order]" value="1" />
    <input name="q[id]" value="111" type="hidden" />
    <input name="result" value="A" type="hidden" />
    <div class="question">Питання <div class="clear"></div></div>
    <div class="answers">
      <div class="answer"><span class="marker">А</span> Один варіант</div>
    </div>
    """
    assert parse_all_questions(minimal) == []


def test_parse_explanation_is_empty_string():
    results = parse_all_questions(SINGLE_BLOCK)
    assert results[0]["explanation"] == ""
