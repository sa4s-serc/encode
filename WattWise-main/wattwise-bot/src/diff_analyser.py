"""
diff_analyser.py — compares energy of changed Python blocks between base and head commits.

Uses the existing WattWise Python backend (extract_features.py + predict_energy.py)
by importing them directly. No duplication of ML logic.
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class BlockResult:
    block_type: str
    start_line: int
    end_line: int
    energy_joules: float
    energy_tier: str
    tier_confidence: float
    cost_per_year: float


@dataclass
class BlockDiff:
    file_path: str
    block_type: str
    start_line: int        # head start line (or base if removed)
    change_type: str       # new | modified | removed
    base: Optional[BlockResult]
    head: Optional[BlockResult]
    cost_delta: float      # head.cost - base.cost (positive = regression)


def _add_python_dir(python_dir: str) -> None:
    """Add the WattWise python/ dir to sys.path so we can import its modules."""
    if python_dir not in sys.path:
        sys.path.insert(0, python_dir)


def _run_wattwise(
    code: str,
    python_dir: str,
    rate_kwh: float,
    calls_per_day: Dict[str, int],
) -> List[BlockResult]:
    """
    Run the WattWise analysis pipeline on a string of Python code.
    Returns a list of BlockResult with cost attached.
    """
    _add_python_dir(python_dir)

    from extract_features import extract_code_blocks  # type: ignore
    from predict_energy import EnergyPredictor        # type: ignore
    from cost import compute_cost_per_year             # type: ignore

    models_dir = os.path.join(python_dir, "models")
    predictor = EnergyPredictor(models_dir=models_dir)

    raw_blocks = extract_code_blocks(code)

    if isinstance(raw_blocks, dict) and "error" in raw_blocks:
        return []

    predictions = predictor.predict_blocks(raw_blocks)

    results: List[BlockResult] = []
    for pred in predictions:
        if pred.get("error"):
            continue
        energy_j = pred.get("energy_joules") or 0.0
        block_type = pred.get("block_type", "FunctionDef")
        results.append(
            BlockResult(
                block_type=block_type,
                start_line=pred["start_line"],
                end_line=pred["end_line"],
                energy_joules=energy_j,
                energy_tier=pred.get("energy_tier", "Unknown"),
                tier_confidence=pred.get("tier_confidence", 0.0),
                cost_per_year=compute_cost_per_year(
                    energy_j, block_type, rate_kwh, calls_per_day
                ),
            )
        )

    return results


def _get_changed_py_files(base_sha: str, head_sha: str, repo_path: str) -> List[str]:
    """Return list of .py file paths changed between base and head (relative to repo root)."""
    result = subprocess.run(
        ["git", "diff", "--name-only", base_sha, head_sha, "--", "*.py"],
        capture_output=True,
        text=True,
        cwd=repo_path,
    )
    if result.returncode != 0:
        print(f"[wattwise] git diff error: {result.stderr}", file=sys.stderr)
        return []
    files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return files


def _git_show(repo_path: str, sha: str, rel_path: str) -> Optional[str]:
    """Return file content at given sha, or None if the file did not exist."""
    result = subprocess.run(
        ["git", "show", f"{sha}:{rel_path}"],
        capture_output=True,
        text=True,
        cwd=repo_path,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _diff_block_lists(
    base_blocks: List[BlockResult],
    head_blocks: List[BlockResult],
    file_path: str,
) -> List[BlockDiff]:
    """
    Match blocks by (block_type, start_line) with ±3 line tolerance.
    Classify each pair as: new | modified | removed.
    Skip unchanged blocks (same tier and negligible cost delta).
    """
    TOLERANCE = 3
    diffs: List[BlockDiff] = []
    matched_head_indices = set()

    for base_b in base_blocks:
        best_match_idx: Optional[int] = None
        best_distance = TOLERANCE + 1

        for idx, head_b in enumerate(head_blocks):
            if idx in matched_head_indices:
                continue
            if head_b.block_type != base_b.block_type:
                continue
            distance = abs(head_b.start_line - base_b.start_line)
            if distance <= TOLERANCE and distance < best_distance:
                best_distance = distance
                best_match_idx = idx

        if best_match_idx is not None:
            matched_head_indices.add(best_match_idx)
            head_b = head_blocks[best_match_idx]
            cost_delta = head_b.cost_per_year - base_b.cost_per_year

            # Skip truly unchanged blocks
            if head_b.energy_tier == base_b.energy_tier and abs(cost_delta) < 0.001:
                continue

            diffs.append(
                BlockDiff(
                    file_path=file_path,
                    block_type=base_b.block_type,
                    start_line=head_b.start_line,
                    change_type="modified",
                    base=base_b,
                    head=head_b,
                    cost_delta=cost_delta,
                )
            )
        else:
            diffs.append(
                BlockDiff(
                    file_path=file_path,
                    block_type=base_b.block_type,
                    start_line=base_b.start_line,
                    change_type="removed",
                    base=base_b,
                    head=None,
                    cost_delta=-base_b.cost_per_year,
                )
            )

    for idx, head_b in enumerate(head_blocks):
        if idx not in matched_head_indices:
            diffs.append(
                BlockDiff(
                    file_path=file_path,
                    block_type=head_b.block_type,
                    start_line=head_b.start_line,
                    change_type="new",
                    base=None,
                    head=head_b,
                    cost_delta=head_b.cost_per_year,
                )
            )

    return diffs


def analyse_pr(
    base_sha: str,
    head_sha: str,
    repo_path: str,
    python_dir: str,
    rate_kwh: float = 8.0,
    calls_per_day: Dict[str, int] | None = None,
) -> List[BlockDiff]:
    """Main entry point. Returns all non-trivial BlockDiff items for a PR."""
    if calls_per_day is None:
        _add_python_dir(python_dir)
        from cost import DEFAULT_CALLS_PER_DAY  # type: ignore
        calls_per_day = DEFAULT_CALLS_PER_DAY

    changed_files = _get_changed_py_files(base_sha, head_sha, repo_path)
    print(f"[wattwise] Changed Python files: {changed_files}", file=sys.stderr)

    all_diffs: List[BlockDiff] = []
    for rel_path in changed_files:
        base_code = _git_show(repo_path, base_sha, rel_path)
        head_code = _git_show(repo_path, head_sha, rel_path)

        base_blocks = (
            _run_wattwise(base_code, python_dir, rate_kwh, calls_per_day)
            if base_code is not None else []
        )
        head_blocks = (
            _run_wattwise(head_code, python_dir, rate_kwh, calls_per_day)
            if head_code is not None else []
        )

        file_diffs = _diff_block_lists(base_blocks, head_blocks, rel_path)
        all_diffs.extend(file_diffs)

    return all_diffs
