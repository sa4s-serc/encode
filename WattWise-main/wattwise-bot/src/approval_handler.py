"""
approval_handler.py — handles /wattwise approve and /wattwise reject slash commands.

Called when the GitHub Actions wattwise-approve.yml workflow fires on an
issue_comment event. Verifies the commenter is an authorised manager, then
updates the status check and labels accordingly.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Optional

import github_api  # type: ignore
import comment_builder  # type: ignore
from config import load_config  # type: ignore


def _parse_command(body: str) -> Optional[tuple[str, str]]:
    """
    Parse /wattwise approve or /wattwise reject [reason].
    Returns (action, reason) or None if not a wattwise command.
    """
    body = body.strip()
    m = re.match(r"^/wattwise\s+(approve|reject)(.*)$", body, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    action = m.group(1).lower()
    reason = m.group(2).strip()
    return action, reason


def handle(event: dict, repo_path: str) -> None:
    """Main entry point for issue_comment events."""
    cfg = load_config(repo_path)

    comment_body: str = event.get("comment", {}).get("body", "")
    commenter: str = event.get("comment", {}).get("user", {}).get("login", "")
    issue_number: int = event.get("issue", {}).get("number", 0)

    # Only act on PR comments (issues don't have pull_request key)
    if "pull_request" not in event.get("issue", {}):
        print("[wattwise] Comment is not on a PR — skipping.", file=sys.stderr)
        return

    parsed = _parse_command(comment_body)
    if parsed is None:
        print("[wattwise] Comment is not a /wattwise command — skipping.", file=sys.stderr)
        return

    action, reason = parsed

    # Verify commenter is an authorised manager
    if commenter not in cfg.managers:
        print(
            f"[wattwise] @{commenter} is not in the managers list — ignoring command.",
            file=sys.stderr,
        )
        # Post a polite reply
        github_api.post_comment(
            issue_number,
            f"@{commenter} — only authorised energy managers can approve or reject this gate.",
        )
        return

    # Look up the PR's head SHA so we can update the status check
    pr_data = github_api.get_pr(issue_number)
    if not pr_data:
        print(f"[wattwise] Could not fetch PR #{issue_number}", file=sys.stderr)
        return
    head_sha: str = pr_data["head"]["sha"]
    pr_author: str = pr_data["user"]["login"]

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if action == "approve":
        github_api.set_status(
            head_sha,
            "success",
            f"Approved by @{commenter} — energy gate passed.",
        )
        github_api.apply_label(issue_number, "energy-approved")
        github_api.remove_label(issue_number, "energy-changes-requested")
        github_api.remove_label(issue_number, "energy-pending")

        # Edit the manager comment to reflect the decision
        existing = github_api.find_bot_comment(issue_number, comment_builder.MGR_COMMENT_MARKER)
        if existing:
            updated_body = comment_builder.build_approval_edit(
                existing["body"],
                decision="approved",
                decided_by=commenter,
                timestamp=timestamp,
            )
            github_api.edit_comment(existing["id"], updated_body)

        # Notify the PR author
        github_api.post_comment(
            issue_number,
            f"✅ @{pr_author} — the energy gate has been **approved** by @{commenter}. "
            f"The merge is now unblocked.",
        )
        print(f"[wattwise] PR #{issue_number} approved by @{commenter}.", file=sys.stderr)

    else:  # reject
        github_api.set_status(
            head_sha,
            "failure",
            f"Changes requested by @{commenter} — energy gate rejected.",
        )
        github_api.apply_label(issue_number, "energy-changes-requested")
        github_api.remove_label(issue_number, "energy-approved")
        github_api.remove_label(issue_number, "energy-pending")

        existing = github_api.find_bot_comment(issue_number, comment_builder.MGR_COMMENT_MARKER)
        if existing:
            updated_body = comment_builder.build_approval_edit(
                existing["body"],
                decision="rejected",
                decided_by=commenter,
                reason=reason,
                timestamp=timestamp,
            )
            github_api.edit_comment(existing["id"], updated_body)

        reason_str = f": {reason}" if reason else "."
        github_api.post_comment(
            issue_number,
            f"❌ @{pr_author} — the energy gate has been **rejected** by @{commenter}{reason_str} "
            f"Please address the energy concerns and update the PR.",
        )
        print(f"[wattwise] PR #{issue_number} rejected by @{commenter}. Reason: {reason}", file=sys.stderr)
