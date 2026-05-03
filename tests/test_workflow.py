import yaml
import pytest
from pathlib import Path

WORKFLOW_PATH = Path(".github/workflows/send_question.yml")


def load_workflow():
    with open(WORKFLOW_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if True in raw and "on" not in raw:
        raw["on"] = raw.pop(True)
    return raw


def test_workflow_file_exists():
    assert WORKFLOW_PATH.exists(), "Workflow file not found"


def test_schedule_trigger_present():
    workflow = load_workflow()
    triggers = workflow.get("on", {})
    assert "schedule" in triggers, "schedule trigger must be present for automated sending"


def test_workflow_dispatch_present():
    workflow = load_workflow()
    triggers = workflow.get("on", {})
    assert "workflow_dispatch" in triggers, "workflow_dispatch trigger must be present"


def test_send_daily_yml_removed():
    assert not Path(".github/workflows/send_daily.yml").exists(), (
        "send_daily.yml is a duplicate of send_question.yml and must be removed"
    )


def test_runs_send_telegram():
    workflow = load_workflow()
    jobs = workflow.get("jobs", {})
    all_steps = [step for job in jobs.values() for step in job.get("steps", [])]
    run_commands = " ".join(str(s.get("run", "")) for s in all_steps)
    assert "send_telegram.py" in run_commands, "workflow must run send_telegram.py"
