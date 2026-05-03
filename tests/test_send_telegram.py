import json
import pytest


def test_no_image_needed_without_url(monkeypatch, tmp_path):
    """Questions with image-requirement keywords but no image_url are filtered out."""
    from send_telegram import load_question

    questions = [
        {"id": "q1", "text": "на рисунку показано схему", "options": {"A": "так"}, "answer": "A"},
        {"id": "q2", "text": "Яка формула правильна?", "options": {"A": "x²"}, "answer": "A"},
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
    (bank_dir / "math.json").write_text(
        json.dumps({"questions": questions}), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    selected_ids = {load_question("math")["id"] for _ in range(60)}

    assert "q1" not in selected_ids, "question needing image without url must be filtered"
    assert selected_ids <= {"q2", "q3"}


def _make_mock(monkeypatch):
    import send_telegram
    payloads = {}

    class MockResp:
        ok = True
        def raise_for_status(self): pass
        def json(self): return {"result": {"message_id": 42}}

    def mock_post(endpoint, **kwargs):
        payloads[endpoint] = kwargs.get("json", {})
        return MockResp()

    monkeypatch.setattr(send_telegram, "_post", mock_post)
    return send_telegram, payloads


def test_send_to_no_image(monkeypatch):
    """No image: sendMessage then sendPoll linked to it."""
    st, payloads = _make_mock(monkeypatch)

    q = {
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


def test_send_to_with_image(monkeypatch):
    """With image: sendPhoto (with caption) then sendPoll linked to it."""
    st, payloads = _make_mock(monkeypatch)

    q = {
        "text": "Що зображено на рисунку?",
        "options": {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"},
        "answer": "B",
        "image": "https://example.com/img.png",
    }
    st.send_to("@channel", "biology", q)

    assert set(payloads) == {"sendPhoto", "sendPoll"}
    assert "caption" in payloads["sendPhoto"], "sendPhoto must carry caption"
    assert payloads["sendPhoto"]["parse_mode"] == "MarkdownV2"
    assert "Що зображено на рисунку" in payloads["sendPhoto"]["caption"]
    assert payloads["sendPoll"]["reply_to_message_id"] == 42
