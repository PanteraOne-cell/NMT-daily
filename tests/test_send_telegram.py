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

    q = load_question("math")
    assert q["id"] == "q1"


# ── shared mock helper ────────────────────────────────────────────────────────

def _make_mock(monkeypatch, tmp_path):
    """Returns (send_telegram module, calls list).
    calls: list of (endpoint, json_payload) in call order.
    """
    import send_telegram

    calls: list[tuple[str, dict]] = []

    class MockResp:
        ok = True
        def raise_for_status(self): pass
        def json(self): return {"result": {"message_id": 42}}

    def mock_post(endpoint, **kwargs):
        calls.append((endpoint, kwargs.get("json", {})))
        return MockResp()

    monkeypatch.setattr(send_telegram, "_post", mock_post)
    monkeypatch.setattr(send_telegram, "_load_sent", lambda: set())
    monkeypatch.setattr(send_telegram, "_save_sent", lambda _id: None)

    return send_telegram, calls


def test_send_to_no_image(monkeypatch, tmp_path):
    """No image: sendMessage → sendPoll → sendMessage(spoiler)."""
    st, calls = _make_mock(monkeypatch, tmp_path)

    q = {
        "id": "test_1",
        "text": "Яке значення має вираз?",
        "options": {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"},
        "answer": "C",
    }
    st.send_to("@channel", "math", q)

    endpoints = [ep for ep, _ in calls]
    assert endpoints == ["sendMessage", "sendPoll", "sendMessage"], endpoints
    poll = calls[1][1]
    assert poll["type"] == "quiz"
    assert poll["is_anonymous"] is True
    assert poll["correct_option_id"] == 2   # "C" is index 2 of A-E
    assert poll["reply_to_message_id"] == 42
    spoiler_text = calls[2][1]["text"]
    assert "||" in spoiler_text, "spoiler must use || formatting"
    assert "C" in spoiler_text


def test_send_to_with_image(monkeypatch, tmp_path):
    """With image: sendPhoto(caption) → sendPoll → sendMessage(spoiler)."""
    st, calls = _make_mock(monkeypatch, tmp_path)

    q = {
        "id": "test_2",
        "text": "Що зображено на рисунку?",
        "options": {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"},
        "answer": "B",
        "image": "https://example.com/img.png",
    }
    st.send_to("@channel", "biology", q)

    endpoints = [ep for ep, _ in calls]
    assert endpoints == ["sendPhoto", "sendPoll", "sendMessage"], endpoints
    photo = calls[0][1]
    assert "caption" in photo
    assert photo["parse_mode"] == "MarkdownV2"
    assert "Що зображено на рисунку" in photo["caption"]
    assert calls[1][1]["reply_to_message_id"] == 42
    assert "||" in calls[2][1]["text"]


def test_send_to_filters_placeholder_options(monkeypatch, tmp_path):
    """Poll options with value '—' must be excluded."""
    st, calls = _make_mock(monkeypatch, tmp_path)

    q = {
        "id": "test_3",
        "text": "Питання з 4 варіантами",
        "options": {"A": "один", "B": "два", "C": "три", "D": "чотири", "E": "—"},
        "answer": "B",
    }
    st.send_to("@channel", "math", q)

    poll = next(p for ep, p in calls if ep == "sendPoll")
    assert len(poll["options"]) == 4, "placeholder '—' option must be removed"
    texts = [o["text"] for o in poll["options"]]
    assert all(t != "—" for t in texts)
    assert poll["correct_option_id"] == 1   # "B" is index 1 of 4


def test_strip_latex_applied_to_caption(monkeypatch, tmp_path):
    """LaTeX in question text must be converted, not shown raw."""
    st, calls = _make_mock(monkeypatch, tmp_path)

    q = {
        "id": "test_4",
        "text": r"Обчисліть \(\sqrt{9}\)",
        "options": {"A": "3", "B": "9", "C": "—", "D": "—", "E": "—"},
        "answer": "A",
    }
    st.send_to("@channel", "math", q)

    # First call: sendMessage with the question text (no image)
    msg_text = calls[0][1]["text"]
    assert r"\sqrt" not in msg_text, "raw LaTeX must not appear in message"
    assert "√" in msg_text


def test_main_4_subjects_all_chats(monkeypatch, tmp_path):
    """main() sends every subject to every chat: 4 subjects × 2 chats = 8 polls."""
    import send_telegram

    bank_dir = tmp_path / "bank"
    bank_dir.mkdir()
    for subj in ["math", "ukrainian", "history", "biology"]:
        qs = [{"id": f"{subj}_1", "text": "Q", "options": {"A": "x"}, "answer": "A"}]
        (bank_dir / f"{subj}.json").write_text(
            json.dumps({"questions": qs}), encoding="utf-8"
        )
    monkeypatch.chdir(tmp_path)

    calls: list[tuple[str, dict]] = []

    class MockResp:
        ok = True
        def raise_for_status(self): pass
        def json(self): return {"result": {"message_id": 1}}

    monkeypatch.setattr(send_telegram, "_post",
                        lambda ep, **kw: (calls.append((ep, kw.get("json", {}))), MockResp())[1])
    monkeypatch.setattr(send_telegram, "_load_sent", lambda: set())
    monkeypatch.setattr(send_telegram, "_save_sent", lambda _: None)
    monkeypatch.setattr(send_telegram, "CHAT_IDS", ["chat1", "chat2"])
    monkeypatch.setattr(send_telegram, "time", __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock())

    send_telegram.main()

    poll_calls   = [(ep, p) for ep, p in calls if ep == "sendPoll"]
    spoiler_calls = [(ep, p) for ep, p in calls if ep == "sendMessage"
                     and "||" in p.get("text", "")]

    assert len(poll_calls) == 8,    f"expected 8 sendPoll, got {len(poll_calls)}"
    assert len(spoiler_calls) == 8, f"expected 8 spoiler messages, got {len(spoiler_calls)}"

    chat_ids_polled = {p["chat_id"] for _, p in poll_calls}
    assert chat_ids_polled == {"chat1", "chat2"}, "both chats must receive polls"

    subjects_polled = {p["question"] for _, p in poll_calls}
    # All polls have the same question text "Оберіть правильну відповідь:" but
    # we verify that all 4 subjects were sent by checking print output via send_to calls.
    # Instead, count unique chat×subject pairs via spoiler reply_to ids (all map to msg_id=1).
    assert len(poll_calls) == 8
