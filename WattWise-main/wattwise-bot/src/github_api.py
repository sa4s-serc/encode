"""
github_api.py — thin wrapper around the GitHub REST API for PR bot operations.

All calls use the GITHUB_TOKEN from the environment. The repo slug
(owner/repo) is read from GITHUB_REPOSITORY env var (set automatically
by GitHub Actions).
"""
from __future__ import annotations

import os
import sys
from typing import Optional

import requests

GITHUB_API = "https://api.github.com"
STATUS_CONTEXT = "wattwise/energy-gate"


def _headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _repo() -> str:
    return os.environ.get("GITHUB_REPOSITORY", "")


# ── Comments ─────────────────────────────────────────────────────────────────

def post_comment(pr_number: int, body: str) -> Optional[int]:
    """Post a new comment to a PR. Returns the comment id."""
    url = f"{GITHUB_API}/repos/{_repo()}/issues/{pr_number}/comments"
    resp = requests.post(url, headers=_headers(), json={"body": body})
    if resp.status_code not in (200, 201):
        print(f"[wattwise] Failed to post comment: {resp.status_code} {resp.text}", file=sys.stderr)
        return None
    return resp.json().get("id")


def edit_comment(comment_id: int, body: str) -> bool:
    """Edit an existing comment by id."""
    url = f"{GITHUB_API}/repos/{_repo()}/issues/comments/{comment_id}"
    resp = requests.patch(url, headers=_headers(), json={"body": body})
    if resp.status_code != 200:
        print(f"[wattwise] Failed to edit comment {comment_id}: {resp.status_code}", file=sys.stderr)
        return False
    return True


def find_bot_comment(pr_number: int, marker: str) -> Optional[dict]:
    """
    Search existing PR comments for one containing `marker`.
    Returns the raw comment dict (with 'id' and 'body') or None.
    """
    url = f"{GITHUB_API}/repos/{_repo()}/issues/{pr_number}/comments"
    page = 1
    while True:
        resp = requests.get(url, headers=_headers(), params={"per_page": 100, "page": page})
        if resp.status_code != 200:
            break
        comments = resp.json()
        if not comments:
            break
        for c in comments:
            if marker in (c.get("body") or ""):
                return c
        if len(comments) < 100:
            break
        page += 1
    return None


def upsert_comment(pr_number: int, body: str, marker: str) -> Optional[int]:
    """
    Post a new comment or edit the existing one that contains `marker`.
    Returns the comment id.
    """
    existing = find_bot_comment(pr_number, marker)
    if existing:
        edit_comment(existing["id"], body)
        return existing["id"]
    return post_comment(pr_number, body)


# ── Status checks ─────────────────────────────────────────────────────────────

def set_status(sha: str, state: str, description: str, target_url: str = "") -> bool:
    """
    Set a commit status check.
    state: 'error' | 'failure' | 'pending' | 'success'
    """
    url = f"{GITHUB_API}/repos/{_repo()}/statuses/{sha}"
    payload: dict = {
        "state": state,
        "context": STATUS_CONTEXT,
        "description": description[:140],  # GitHub limit
    }
    if target_url:
        payload["target_url"] = target_url
    resp = requests.post(url, headers=_headers(), json=payload)
    if resp.status_code not in (200, 201):
        print(f"[wattwise] Failed to set status: {resp.status_code} {resp.text}", file=sys.stderr)
        return False
    return True


# ── Labels ────────────────────────────────────────────────────────────────────

def apply_label(pr_number: int, label: str) -> bool:
    """Apply a label to a PR. Creates the label if it doesn't exist."""
    _ensure_label_exists(label)
    url = f"{GITHUB_API}/repos/{_repo()}/issues/{pr_number}/labels"
    resp = requests.post(url, headers=_headers(), json={"labels": [label]})
    if resp.status_code not in (200, 201):
        print(f"[wattwise] Failed to apply label '{label}': {resp.status_code}", file=sys.stderr)
        return False
    return True


def remove_label(pr_number: int, label: str) -> bool:
    """Remove a label from a PR (silently ignores 404)."""
    url = f"{GITHUB_API}/repos/{_repo()}/issues/{pr_number}/labels/{label}"
    resp = requests.delete(url, headers=_headers())
    return resp.status_code in (200, 204, 404)


def _ensure_label_exists(label: str) -> None:
    """Create the label if it doesn't exist (colour-coded by type)."""
    colors = {
        "energy-approved": "0e8a16",
        "energy-changes-requested": "e11d48",
        "energy-pending": "f59e0b",
    }
    url = f"{GITHUB_API}/repos/{_repo()}/labels"
    color = colors.get(label, "6366f1")
    resp = requests.post(url, headers=_headers(), json={"name": label, "color": color})
    # 422 = label already exists, that's fine
    if resp.status_code not in (200, 201, 422):
        print(f"[wattwise] Could not ensure label '{label}': {resp.status_code}", file=sys.stderr)


# ── PR metadata ───────────────────────────────────────────────────────────────

def get_pr(pr_number: int) -> Optional[dict]:
    url = f"{GITHUB_API}/repos/{_repo()}/pulls/{pr_number}"
    resp = requests.get(url, headers=_headers())
    if resp.status_code != 200:
        return None
    return resp.json()
