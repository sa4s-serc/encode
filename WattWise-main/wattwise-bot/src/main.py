#!/usr/bin/env python3
"""
main.py — entry point for the WattWise PR bot.

Routing:
  - GITHUB_EVENT_NAME=pull_request  → run energy diff analysis, post comments, set status
  - GITHUB_EVENT_NAME=issue_comment → handle /wattwise approve|reject commands
"""
from __future__ import annotations

import json
import os
import sys

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)


def _load_event() -> dict:
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not event_path or not os.path.exists(event_path):
        return {}
    with open(event_path, "r") as f:
        return json.load(f)


def _write_step_summary(content: str) -> None:
    """Write markdown to the GitHub Actions step summary panel."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if not summary_path:
        return
    with open(summary_path, "a", encoding="utf-8") as f:
        f.write(content + "\n")


def handle_pull_request(event: dict, repo_path: str, python_dir: str) -> None:
    import github_api
    import diff_analyser
    import comment_builder
    from config import load_config

    cfg = load_config(repo_path)

    base_sha: str = (
        os.environ.get("PR_BASE_SHA")
        or event.get("pull_request", {}).get("base", {}).get("sha", "")
    )
    head_sha: str = (
        os.environ.get("PR_HEAD_SHA")
        or event.get("pull_request", {}).get("head", {}).get("sha", "")
    )
    pr_number: int = int(
        os.environ.get("PR_NUMBER")
        or event.get("pull_request", {}).get("number", 0)
    )
    pr_author: str = event.get("pull_request", {}).get("user", {}).get("login", "unknown")
    pr_title:  str = event.get("pull_request", {}).get("title", "")

    if not base_sha or not head_sha or not pr_number:
        print("[wattwise] Missing PR context (base_sha, head_sha, pr_number).", file=sys.stderr)
        sys.exit(1)

    print(f"[wattwise] Analysing PR #{pr_number}: {base_sha[:8]}...{head_sha[:8]}", file=sys.stderr)

    github_api.set_status(head_sha, "pending", "WattWise energy analysis in progress…")

    diffs = diff_analyser.analyse_pr(
        base_sha=base_sha,
        head_sha=head_sha,
        repo_path=repo_path,
        python_dir=python_dir,
        rate_kwh=cfg.cost.rate_kwh,
        calls_per_day=cfg.cost.default_calls_per_day,
    )

    new_high_blocks = sum(
        1 for d in diffs
        if d.change_type == "new" and d.head and d.head.energy_tier == "High"
    )
    net_cost_delta   = sum(d.cost_delta for d in diffs)
    gate_triggered   = (
        new_high_blocks > cfg.max_new_high_blocks
        or net_cost_delta > cfg.regression_threshold_cost
    )
    requires_approval = gate_triggered and cfg.require_manager_approval

    dev_body = comment_builder.build_developer_comment(
        diffs=diffs,
        pr_author=pr_author,
        require_approval=requires_approval,
        block_on_gate_failure=cfg.block_on_gate_failure,
        max_new_high_blocks=cfg.max_new_high_blocks,
        regression_threshold_cost=cfg.regression_threshold_cost,
    )
    github_api.upsert_comment(pr_number, dev_body, comment_builder.DEV_COMMENT_MARKER)

    if requires_approval:
        affected_files = sorted({d.file_path for d in diffs})
        mgr_body = comment_builder.build_manager_comment(
            diffs=diffs,
            pr_author=pr_author,
            pr_number=pr_number,
            pr_title=pr_title,
            affected_files=affected_files,
            rate_kwh=cfg.cost.rate_kwh,
            manager_handles=cfg.managers,
        )
        github_api.upsert_comment(pr_number, mgr_body, comment_builder.MGR_COMMENT_MARKER)
        github_api.apply_label(pr_number, "energy-pending")

    # ── GitHub Actions step summary ───────────────────────────────────────
    improved  = sum(1 for d in diffs if d.cost_delta < -0.001)
    regressed = sum(1 for d in diffs if d.cost_delta > 0.001)
    verdict   = "FAILED" if (gate_triggered and cfg.block_on_gate_failure) else "PASSED"
    verdict_icon = "❌" if verdict == "FAILED" else "✅"

    _write_step_summary(f"""## {verdict_icon} WattWise Energy Gate — {verdict}

| Metric | Value |
|--------|-------|
| Net annual cost impact | **{net_cost_delta:+.4f} ₹/yr** |
| New High-energy blocks | **{new_high_blocks}** |
| Blocks improved | {improved} |
| Blocks regressed | {regressed} |
| Gate threshold (High blocks) | {cfg.max_new_high_blocks} |
| Gate threshold (cost) | ₹{cfg.regression_threshold_cost}/yr |
| Manager approval required | {"Yes" if requires_approval else "No"} |
""")

    # ── Set final commit status ───────────────────────────────────────────
    if gate_triggered and cfg.block_on_gate_failure:
        github_api.set_status(
            head_sha,
            "failure",
            f"Energy regression — {new_high_blocks} new High block(s), "
            f"net {net_cost_delta:+.2f} Rs/yr. Manager approval required.",
        )
        print(f"[wattwise] Gate FAILED — {new_high_blocks} new High blocks, net {net_cost_delta:+.4f} Rs/yr", file=sys.stderr)
    elif gate_triggered and not cfg.block_on_gate_failure:
        github_api.set_status(
            head_sha,
            "success",
            f"Energy warning (warn-only) — net {net_cost_delta:+.2f} Rs/yr.",
        )
        print("[wattwise] Gate triggered but block_on_gate_failure=false — warn only.", file=sys.stderr)
    else:
        github_api.set_status(head_sha, "success", "Energy gate passed.")
        print("[wattwise] Gate PASSED.", file=sys.stderr)


def handle_issue_comment(event: dict, repo_path: str) -> None:
    import approval_handler
    approval_handler.handle(event, repo_path)


def main() -> None:
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    repo_path  = os.environ.get("REPO_PATH", os.environ.get("GITHUB_WORKSPACE", os.getcwd()))
    python_dir = os.environ.get("PYTHON_DIR", os.path.join(repo_path, "python"))

    if python_dir not in sys.path:
        sys.path.insert(0, python_dir)
    if _SRC_DIR not in sys.path:
        sys.path.insert(0, _SRC_DIR)

    event = _load_event()

    print(f"[wattwise] Event: {event_name}", file=sys.stderr)

    if event_name == "pull_request":
        handle_pull_request(event, repo_path, python_dir)
    elif event_name == "issue_comment":
        handle_issue_comment(event, repo_path)
    else:
        print(f"[wattwise] Unhandled event type: '{event_name}'.", file=sys.stderr)


if __name__ == "__main__":
    main()
