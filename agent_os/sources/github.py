"""sources/github.py — GitHub event normalizer.

Converts GitHub webhook payloads into canonical Signal format.
See TRD.md for full event-to-metric mapping.
"""

from __future__ import annotations

from typing import Any


def normalize(event_type: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Convert GitHub event to canonical Signal format.

    Returns: {metric_name, value, timestamp, metadata} or None if unsupported.
    """

    # ── push ───────────────────────────────────────────────────────
    if event_type == "push":
        commits = payload.get("commits", [])
        return {
            "metric_name": "github.push.count",
            "value": float(len(commits)),
            "timestamp": payload.get("head_commit", {}).get("timestamp"),
            "metadata": {
                "repository": payload.get("repository", {}).get("full_name"),
                "branch": payload.get("ref", "").replace("refs/heads/", ""),
                "pusher": payload.get("pusher", {}).get("name"),
                "forced": payload.get("forced", False),
            },
        }

    # ── pull_request ───────────────────────────────────────────────
    elif event_type == "pull_request":
        pr = payload.get("pull_request", {})
        action = payload.get("action")

        if action == "opened":
            return {
                "metric_name": "github.pr.opened",
                "value": 1.0,
                "timestamp": pr.get("created_at"),
                "metadata": {
                    "repository": payload.get("repository", {}).get("full_name"),
                    "author": pr.get("user", {}).get("login"),
                    "base_branch": pr.get("base", {}).get("ref"),
                    "head_branch": pr.get("head", {}).get("ref"),
                    "number": pr.get("number"),
                },
            }
        elif action == "closed":
            return {
                "metric_name": "github.pr.merged",
                "value": 1.0 if pr.get("merged") else 0.0,
                "timestamp": pr.get("closed_at"),
                "metadata": {
                    "repository": payload.get("repository", {}).get("full_name"),
                    "author": pr.get("user", {}).get("login"),
                    "number": pr.get("number"),
                    "merge_time_hours": _compute_hours_between(
                        pr.get("created_at"), pr.get("merged_at")
                    ),
                },
            }

    # ── issues ─────────────────────────────────────────────────────
    elif event_type == "issues":
        issue = payload.get("issue", {})
        action = payload.get("action")
        timestamp = (
            issue.get("created_at") if action == "opened" else issue.get("closed_at")
        )
        return {
            "metric_name": f"github.issue.{action}",
            "value": 1.0,
            "timestamp": timestamp,
            "metadata": {
                "repository": payload.get("repository", {}).get("full_name"),
                "author": issue.get("user", {}).get("login"),
                "labels": [label.get("name") for label in issue.get("labels", [])],
                "number": issue.get("number"),
            },
        }

    # ── workflow_run ───────────────────────────────────────────────
    elif event_type == "workflow_run":
        run = payload.get("workflow_run", {})
        conclusion = run.get("conclusion")
        return {
            "metric_name": "github.ci.status",
            "value": 1.0 if conclusion == "success" else 0.0,
            "timestamp": run.get("updated_at"),
            "metadata": {
                "repository": payload.get("repository", {}).get("full_name"),
                "workflow": run.get("name"),
                "status": run.get("status"),
                "conclusion": conclusion,
                "duration_minutes": _compute_minutes_between(
                    run.get("started_at"), run.get("completed_at")
                ),
            },
        }

    # ── deployment ─────────────────────────────────────────────────
    elif event_type == "deployment":
        deployment = payload.get("deployment", {})
        return {
            "metric_name": "github.deployment.count",
            "value": 1.0,
            "timestamp": deployment.get("created_at"),
            "metadata": {
                "repository": payload.get("repository", {}).get("full_name"),
                "environment": deployment.get("environment"),
                "deployer": deployment.get("creator", {}).get("login"),
            },
        }

    # Unsupported event type
    return None


def _compute_hours_between(start: str | None, end: str | None) -> float | None:
    """Compute time difference in hours between two ISO timestamps."""
    if not start or not end:
        return None
    try:
        from datetime import datetime, timezone

        dt_start = datetime.fromisoformat(start.replace("Z", "+00:00"))
        dt_end = datetime.fromisoformat(end.replace("Z", "+00:00"))
        delta = dt_end - dt_start
        return delta.total_seconds() / 3600.0
    except Exception:
        return None


def _compute_minutes_between(start: str | None, end: str | None) -> float | None:
    """Compute time difference in minutes between two ISO timestamps."""
    if not start or not end:
        return None
    try:
        from datetime import datetime, timezone

        dt_start = datetime.fromisoformat(start.replace("Z", "+00:00"))
        dt_end = datetime.fromisoformat(end.replace("Z", "+00:00"))
        delta = dt_end - dt_start
        return delta.total_seconds() / 60.0
    except Exception:
        return None
