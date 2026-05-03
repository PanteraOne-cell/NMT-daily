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


def test_send_to_calls_sendpoll(monkeypatch):
    """send_to: sends context message then a linked quiz poll."""
    import send_telegram

    calls = []
    msg_id = 42

    class MockResp:
        ok = True

        def raise_for_status(self):
            pass

        def json(self):
            return {"result": {"message_id": msg_id}}

    def mock_post(endpoint, **kwargs):
        calls.append((endpoint, kwargs.get("json", {})))
        return MockResp()

    monkeypatch.setattr(send_telegram, "_post", mock_post)

    q = {
        "text": "Яке значення має вираз?",
        "options": {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"},
        "answer": "C",
    }
    send_telegram.send_to("@channel", "math", q)

    assert len(calls) == 2, "send_to must make exactly 2 API calls (message + poll)"
    assert calls[0][0] == "sendMessage"
    endpoint, payload = calls[1]
    assert endpoint == "sendPoll"
    assert payload["type"] == "quiz"
    assert payload["is_anonymous"] is True
    assert payload["correct_option_id"] == 2       # index of "C" in options
    assert payload["reply_to_message_id"] == msg_id


def test_send_to_with_image(monkeypatch):
    """send_to: uses sendPhoto instead of sendMessage when image is present."""
    import send_telegram

    calls = []

    class MockResp:
        ok = True

        def raise_for_status(self):
            pass

        def json(self):
            return {"result": {"message_id": 7}}

    def mock_post(endpoint, **kwargs):
        calls.append(endpoint)
        return MockResp()

    monkeypatch.setattr(send_telegram, "_post", mock_post)

    q = {
        "text": "на рисунку показано графік",
        "options": {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"},
        "answer": "A",
        "image": "https://example.com/img.png",
    }
    send_telegram.send_to("@channel", "math", q)

    assert calls == ["sendPhoto", "sendPoll"]
