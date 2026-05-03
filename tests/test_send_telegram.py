import json
import pytest


def test_no_image_needed_without_url(monkeypatch, tmp_path):
    """Questions requiring an image but lacking one are filtered out."""
    from send_telegram import load_question

    questions = [
        {"id": "q1", "text": "на рисунку показано схему", "options": {"A": "так"}, "answer": "A"},
        {"id": "q2", "text": "Яка формула правильна?",    "options": {"A": "x²"},  "answer": "A"},
        {
            "id": "q3",
            "text": "на рисунку показано графік",
            "options": {"A": "так"},
            "answer": "A",
            "image_url": "https://example.com/img.png",
        },
    ]
    bank_dir = tmp_path / "bank"
    bank_dir.mkdir()
    (bank_dir / "math.json").write_text(json.dumps({"questions": questions}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    selected_ids = {load_question("math")["id"] for _ in range(60)}
    assert "q1" not in selected_ids, "question needing image without url must be filtered"
    assert selected_ids <= {"q2", "q3"}


def test_sent_tracking_excludes_recent(monkeypatch, tmp_path):
    """load_question skips questions that appear in data/sent.json."""
    from send_telegram import load_question

    questions = [
        {"id": "q1", "text": "Питання 1", "options": {"A": "варіант"}, "answer": "A"},
        {"id": "q2", "text": "Питання 2", "options": {"A": "варіант"}, "answer": "A"},
    ]
    bank_dir = tmp_path / "bank"
    bank_dir.mkdir()
    (bank_dir / "math.json").write_text(json.dumps({"questions": questions}), encoding="utf-8")

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "sent.json").write_text(json.dumps({"sent": ["q1"]}), encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    selected = {load_question("math")["id"] for _ in range(40)}
    assert selected == {"q2"}, "recently sent q1 must be excluded"


def test_sent_tracking_fallback(monkeypatch, tmp_path):
    """When all questions were sent recently, fall back to the full pool."""
    from send_telegram import load_question

    questions = [{"id": "q1", "text": "X", "options": {"A": "a"}, "answer": "A"}]
    bank_dir = tmp_path / "bank"
    bank_dir.mkdir()
    (bank_dir / "math.json").write_text(json.dumps({"questions": questions}), encoding="utf-8")

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "sent.json").write_text(json.dumps({"sent": ["q1"]}), encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    # Must not raise — falls back to full pool
    q = load_question("math")
    assert q["id"] == "q1"


# ── shared mock helper ────────────────────────────────────────────────────────

def _make_mock(monkeypatch, tmp_path):
    import send_telegram

    payloads: dict = {}

    class MockResp:
        ok = True
        def raise_for_status(self): pass
        def json(self): return {"result": {"message_id": 42}}

    def mock_post(endpoint, **kwargs):
        payloads[endpoint] = kwargs.get("json", {})
        return MockResp()

    monkeypatch.setattr(send_telegram, "_post", mock_post)

    # neutralise sent tracking I/O
    monkeypatch.setattr(send_telegram, "_load_sent", lambda: set())
    monkeypatch.setattr(send_telegram, "_save_sent", lambda _id: None)

    return send_telegram, payloads


def test_send_to_no_image(monkeypatch, tmp_path):
    """No image: sendMessage then sendPoll linked to it."""
    st, payloads = _make_mock(monkeypatch, tmp_path)

    q = {
        "id": "test_1",
        "text": "Яке значення має вираз?",
        "options": {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"},
        "answer": "C",
    }
    st.send_to("@channel", "math", q)

    assert set(payloads) == {"sendMessage", "sendPoll"}
    assert payloads["sendPoll"]["type"] == "quiz"
    assert payloads["sendPoll"]["is_anonymous"] is True
    assert payloads["sendPoll"]["correct_option_id"] == 2   # "C" is index 2
    assert payloads["sendPoll"]["reply_to_message_id"] == 42


def test_send_to_with_image(monkeypatch, tmp_path):
    """With image: sendPhoto (with caption) then sendPoll linked to it."""
    st, payloads = _make_mock(monkeypatch, tmp_path)

    q = {
        "id": "test_2",
        "text": "Що зображено на рисунку?",
        "options": {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"},
        "answer": "B",
        "image": "https://example.com/img.png",
    }
    st.send_to("@channel", "biology", q)

    assert set(payloads) == {"sendPhoto", "sendPoll"}
    assert "caption" in payloads["sendPhoto"]
    assert payloads["sendPhoto"]["parse_mode"] == "MarkdownV2"
    assert "Що зображено на рисунку" in payloads["sendPhoto"]["caption"]
    assert payloads["sendPoll"]["reply_to_message_id"] == 42


def test_send_to_filters_placeholder_options(monkeypatch, tmp_path):
    """Poll options with value '—' (placeholder) must be excluded."""
    st, payloads = _make_mock(monkeypatch, tmp_path)

    q = {
        "id": "test_3",
        "text": "Питання з 4 варіантами",
        "options": {"A": "один", "B": "два", "C": "три", "D": "чотири", "E": "—"},
        "answer": "B",
    }
    st.send_to("@channel", "math", q)

    poll_opts = payloads["sendPoll"]["options"]
    assert len(poll_opts) == 4, "placeholder '—' option must be removed"
    texts = [o["text"] for o in poll_opts]
    assert all(t != "—" for t in texts)
    assert payloads["sendPoll"]["correct_option_id"] == 1   # "B" is index 1 of 4


def test_strip_latex_applied_to_caption(monkeypatch, tmp_path):
    """LaTeX in question text must be converted in caption, not shown raw."""
    st, payloads = _make_mock(monkeypatch, tmp_path)

    q = {
        "id": "test_4",
        "text": r"Обчисліть \(\sqrt{9}\)",
        "options": {"A": "3", "B": "9", "C": "—", "D": "—", "E": "—"},
        "answer": "A",
    }
    st.send_to("@channel", "math", q)

    msg_text = payloads["sendMessage"]["text"]
    assert r"\sqrt" not in msg_text, "raw LaTeX must not appear in caption"
    assert "√9" in msg_text or "√" in msg_text
