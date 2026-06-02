"""
comment_builder.py — renders developer and manager PR comments as GitHub-flavoured markdown.
"""
from __future__ import annotations

from typing import List, Tuple

from diff_analyser import BlockDiff  # type: ignore
from cost import compute_co2_delta_kg  # type: ignore

# Unique HTML markers so the bot can find and edit its own comments
DEV_COMMENT_MARKER = "<!-- wattwise-dev-comment -->"
MGR_COMMENT_MARKER = "<!-- wattwise-mgr-comment -->"

TIER_EMOJI = {"Low": "🟢", "Medium": "🟡", "High": "🔴", "Unknown": "⚪"}
CHANGE_EMOJI = {"new": "➕", "modified": "✏️", "removed": "➖"}

# Rows to show inline before collapsing the rest into <details>
TABLE_INLINE_LIMIT = 15


def _tier(tier: str) -> str:
    return f"{TIER_EMOJI.get(tier, '⚪')} {tier}"


def _fmt_cost(inr: float) -> str:
    """Format an INR amount with sign. Uses enough precision to be meaningful."""
    sign = "+" if inr > 0 else ("-" if inr < 0 else "")
    abs_val = abs(inr)
    if abs_val == 0:
        return "₹0.00/yr"
    elif abs_val >= 100:
        return f"{sign}₹{abs_val:,.0f}/yr"
    elif abs_val >= 1:
        return f"{sign}₹{abs_val:.2f}/yr"
    elif abs_val >= 0.01:
        return f"{sign}₹{abs_val:.4f}/yr"
    else:
        # Show in paise (1 ₹ = 100 paise) for very small values
        paise = abs_val * 100
        return f"{sign}{paise:.2f}p/yr"


def _summarise(diffs: List[BlockDiff]) -> Tuple[int, int, int, float, int]:
    """Return (new_count, improved_count, regressed_count, net_cost_delta, new_high_count)."""
    new_count = sum(1 for d in diffs if d.change_type == "new")
    improved = sum(1 for d in diffs if d.cost_delta < -0.001)
    regressed = sum(1 for d in diffs if d.cost_delta > 0.001)
    net_delta = sum(d.cost_delta for d in diffs)
    new_high = sum(
        1 for d in diffs
        if d.change_type == "new" and d.head and d.head.energy_tier == "High"
    )
    return new_count, improved, regressed, net_delta, new_high


def _build_table_rows(diffs: List[BlockDiff]) -> List[str]:
    """Build markdown table rows sorted by absolute cost impact (largest first)."""
    sorted_diffs = sorted(diffs, key=lambda d: abs(d.cost_delta), reverse=True)
    rows = []
    for d in sorted_diffs:
        before = _tier(d.base.energy_tier) if d.base else "—"
        after  = _tier(d.head.energy_tier) if d.head else "—"
        icon   = CHANGE_EMOJI.get(d.change_type, "")
        rows.append(
            f"| `{d.file_path}` | {icon} `{d.block_type}` "
            f"| {d.start_line} | {before} | {after} | {_fmt_cost(d.cost_delta)} |"
        )
    return rows


def build_developer_comment(
    diffs: List[BlockDiff],
    pr_author: str,
    require_approval: bool,
    block_on_gate_failure: bool,
    max_new_high_blocks: int,
    regression_threshold_cost: float,
) -> str:
    new_count, improved, regressed, net_delta, new_high = _summarise(diffs)
    gate_triggered = (
        new_high > max_new_high_blocks or net_delta > regression_threshold_cost
    )

    # ── Banner ───────────────────────────────────────────────────────────
    if net_delta < -0.001:
        banner = "🟢 **Energy improvement** — this PR reduces estimated annual energy cost."
        banner_bg = "tip"
    elif gate_triggered:
        banner = "🔴 **Energy regression** — this PR increases estimated energy cost above the threshold."
        banner_bg = "warning"
    else:
        banner = "⚪ **No significant energy change** detected in this PR."
        banner_bg = "note"

    lines: List[str] = [
        DEV_COMMENT_MARKER,
        "## ⚡ WattWise Energy Gate",
        "",
        f"> [!{banner_bg.upper()}]",
        f"> {banner}",
        "",
    ]

    # ── Metric pills ─────────────────────────────────────────────────────
    lines += [
        "| Metric | Value |",
        "|--------|-------|",
        f"| Net annual cost impact | **{_fmt_cost(net_delta)}** |",
        f"| New blocks introduced | {new_count} |",
        f"| New 🔴 High-energy blocks | **{new_high}** |",
        f"| Blocks improved | {improved} |",
        f"| Blocks regressed | {regressed} |",
        "",
    ]

    # ── Block diff table ──────────────────────────────────────────────────
    if diffs:
        header = [
            "### Block-level energy diff",
            "",
            "| File | Block | Line | Before | After | Cost Δ/yr |",
            "|------|-------|-----:|--------|-------|----------:|",
        ]
        rows = _build_table_rows(diffs)

        if len(rows) <= TABLE_INLINE_LIMIT:
            lines += header + rows + [""]
        else:
            # Show top N inline, collapse the rest
            lines += header + rows[:TABLE_INLINE_LIMIT] + [""]
            lines += [
                f"<details><summary>Show {len(rows) - TABLE_INLINE_LIMIT} more blocks…</summary>",
                "",
                "| File | Block | Line | Before | After | Cost Δ/yr |",
                "|------|-------|-----:|--------|-------|----------:|",
            ]
            lines += rows[TABLE_INLINE_LIMIT:]
            lines += ["", "</details>", ""]
    else:
        lines += ["*No block-level changes detected.*", ""]

    # ── Gate verdict ──────────────────────────────────────────────────────
    lines += ["---", ""]
    if gate_triggered and require_approval:
        lines += ["### 🚫 Approval required", ""]
        if new_high > max_new_high_blocks:
            lines.append(
                f"- **{new_high} new High-energy block(s)** exceed the limit "
                f"(`max_new_high_blocks: {max_new_high_blocks}` in `.wattwise.yml`)"
            )
        if net_delta > regression_threshold_cost:
            lines.append(
                f"- **Net cost {_fmt_cost(net_delta)}** exceeds the regression threshold "
                f"(`regression_threshold_cost: {regression_threshold_cost}` in `.wattwise.yml`)"
            )
        lines.append("")
        if block_on_gate_failure:
            lines += [
                "> [!CAUTION]",
                "> Merge is **blocked** until an energy manager approves.",
                "",
            ]
    else:
        lines += [
            "> [!TIP]",
            "> Energy gate **passed** — no manager approval required.",
            "",
        ]

    lines += [
        "<sub>⚡ [WattWise](https://github.com/ShailenderGoyal/WattWise) · "
        "Energy estimates use pre-trained ML models · "
        "Cost at ₹8/kWh, India grid · "
        "CO₂ at 0.716 kg/kWh (CEA 2023)</sub>",
    ]

    return "\n".join(lines)


def build_manager_comment(
    diffs: List[BlockDiff],
    pr_author: str,
    pr_number: int,
    pr_title: str,
    affected_files: List[str],
    rate_kwh: float,
    manager_handles: List[str],
) -> str:
    new_count, improved, regressed, net_delta, new_high = _summarise(diffs)
    co2_delta_kg = compute_co2_delta_kg(net_delta, rate_kwh)

    mentions = " ".join(f"@{m}" for m in manager_handles) if manager_handles else ""

    lines: List[str] = [
        MGR_COMMENT_MARKER,
        "## 🔋 WattWise — Manager Approval Required",
        "",
    ]

    if mentions:
        lines += [f"**Attention:** {mentions}", ""]

    lines += [
        f"**PR #{pr_number}** · @{pr_author} · *{pr_title}*",
        "",
        "### Business Impact",
        "",
        "| | |",
        "|---|---|",
        f"| 💰 Annual cost impact | **{_fmt_cost(net_delta)}** |",
        f"| 🌿 CO₂ delta | **{co2_delta_kg:+.3f} kg/yr** |",
        f"| 🔴 New High-energy blocks | **{new_high}** |",
        f"| 🟢 Blocks improved | {improved} |",
        f"| 📁 Files affected | {len(affected_files)} |",
        "",
    ]

    if affected_files:
        files_str = " · ".join(f"`{f}`" for f in affected_files[:6])
        if len(affected_files) > 6:
            files_str += f" · *+{len(affected_files) - 6} more*"
        lines += [files_str, ""]

    lines += [
        "---",
        "### Action required",
        "",
        "Reply with a slash command:",
        "",
        "```",
        "/wattwise approve",
        "/wattwise reject [reason]",
        "```",
        "",
        "> Only listed energy managers can approve or reject.",
        "",
        "<sub>⚡ WattWise Energy Gate · Cost at ₹8/kWh · CO₂ at 0.716 kg/kWh (CEA 2023)</sub>",
    ]

    return "\n".join(lines)


def build_approval_edit(
    original_body: str,
    decision: str,       # "approved" | "rejected"
    decided_by: str,
    reason: str = "",
    timestamp: str = "",
) -> str:
    """Append a decision block to the existing manager comment."""
    icon  = "✅" if decision == "approved" else "❌"
    label = "APPROVED" if decision == "approved" else "CHANGES REQUESTED"

    block = ["", "---", f"### {icon} {label}", f"**By:** @{decided_by}"]
    if timestamp:
        block.append(f"**At:** {timestamp}")
    if reason:
        block.append(f"**Reason:** {reason}")

    return original_body + "\n" + "\n".join(block)
