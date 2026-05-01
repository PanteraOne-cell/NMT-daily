#!/usr/bin/env python3
"""Trigger the send_daily workflow via GitHub API.

Required environment variables:
  GITHUB_TOKEN  — personal access token with 'workflow' scope
  GITHUB_REPO   — repository in 'owner/repo' format
"""

import os
import sys
import requests

WORKFLOW_FILE = "send_daily.yml"
REF = "main"

ERROR_HINTS = {
    401: "Invalid or expired GITHUB_TOKEN. Make sure the token has 'workflow' scope.",
    404: "Repository not found or token lacks access. Check GITHUB_REPO format (owner/repo).",
    422: "Workflow file not found or ref is invalid. Verify the workflow exists on the branch.",
}


def trigger(token: str, repo: str) -> None:
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"ref": REF},
        timeout=15,
    )

    if resp.status_code == 204:
        print(f"OK: workflow dispatched → {repo} ({WORKFLOW_FILE})")
        return

    hint = ERROR_HINTS.get(resp.status_code, "")
    msg = f"ERROR {resp.status_code}: {resp.text.strip()}"
    if hint:
        msg += f"\nHint: {hint}"
    print(msg)
    sys.exit(1)


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPO", "")

    missing = [name for name, val in [("GITHUB_TOKEN", token), ("GITHUB_REPO", repo)] if not val]
    if missing:
        print(f"ERROR: missing environment variable(s): {', '.join(missing)}")
        sys.exit(1)

    trigger(token, repo)


if __name__ == "__main__":
    main()
