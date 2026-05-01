import yaml
import pytest
from pathlib import Path

WORKFLOW_PATH = Path(".github/workflows/send_daily.yml")


def load_workflow():
    with open(WORKFLOW_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    # PyYAML 1.1 parses bare `on` as boolean True; normalize it back to "on"
    if True in raw and "on" not in raw:
        raw["on"] = raw.pop(True)
    return raw


def test_workflow_file_exists():
    assert WORKFLOW_PATH.exists(), "Workflow file not found"


def test_no_schedule_trigger():
    workflow = load_workflow()
    triggers = workflow.get("on", {})
    assert "schedule" not in triggers, (
        "schedule trigger must be removed — use workflow_dispatch only"
    )


def test_workflow_dispatch_present():
    workflow = load_workflow()
    triggers = workflow.get("on", {})
    assert "workflow_dispatch" in triggers, (
        "workflow_dispatch trigger must be present"
    )


def test_no_cron_string_in_file():
    content = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "cron:" not in content, (
        "File must not contain any cron: expression"
    )
