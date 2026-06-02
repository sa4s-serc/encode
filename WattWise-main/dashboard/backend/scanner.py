from __future__ import annotations

import csv
import io
import math
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, List

import yaml

from .cost import AWS_RATE_KWH, CO2_KG_PER_KWH, DEFAULT_CALLS_PER_DAY, annual_co2_kg, annual_cost_usd, annual_kwh
from .models import BlockResult, CostConfig, FeatureDriver, FileResult, HistoryPoint, ScanResult, TreeNode
from .wattwise_bridge import WattWiseBridge

IGNORED_SEGMENTS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "env",
    "myvenv",
    "node_modules",
    "out",
    "venv",
}

DRIVER_META = [
    {"key": "feature_cognitive_complexity", "label": "cognitive complexity", "weight": 1.35, "minimum": 2},
    {"key": "feature_cyclomatic_complexity", "label": "branch complexity", "weight": 1.25, "minimum": 2},
    {"key": "feature_nesting_complexity", "label": "deep nesting", "weight": 1.20, "minimum": 2},
    {"key": "feature_control_flow_complexity", "label": "many execution paths", "weight": 1.10, "minimum": 2},
    {"key": "feature_program_effort", "label": "high Halstead effort", "weight": 1.20, "minimum": 50},
    {"key": "feature_program_volume", "label": "large logic surface", "weight": 1.05, "minimum": 15},
    {"key": "feature_total_nodes", "label": "large AST footprint", "weight": 1.10, "minimum": 20},
    {"key": "feature_max_depth", "label": "deep syntax tree", "weight": 1.00, "minimum": 3},
    {"key": "feature_call_density", "label": "call-heavy body", "weight": 1.15, "minimum": 0.1},
    {"key": "feature_attribute_density", "label": "attribute-heavy access", "weight": 0.90, "minimum": 0.1},
    {"key": "feature_operator_density", "label": "dense operator usage", "weight": 0.85, "minimum": 0.1},
    {"key": "feature_loops_count", "label": "loop-heavy structure", "weight": 1.00, "minimum": 1},
    {"key": "feature_conditionals_count", "label": "conditional-heavy structure", "weight": 1.00, "minimum": 1},
    {"key": "feature_try_blocks_count", "label": "exception-heavy control flow", "weight": 0.95, "minimum": 1},
]


def normalize_repo_path(repo_path: str) -> str:
    return str(Path(repo_path).expanduser().resolve())


def normalize_relative_path(root_path: str, absolute_path: str) -> str:
    return str(Path(absolute_path).resolve().relative_to(Path(root_path).resolve())).replace("\\", "/")


def count_loc(code: str) -> int:
    return sum(1 for line in code.splitlines() if line.strip())


def get_git_value(repo_path: str, args: List[str], fallback: str) -> str:
    try:
        output = subprocess.run(
            ["git", *args],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if output.returncode == 0 and output.stdout.strip():
            return output.stdout.strip()
    except Exception:
        pass
    return fallback


def get_repo_meta(repo_path: str) -> Dict[str, str]:
    normalized = normalize_repo_path(repo_path)
    root = Path(normalized)
    return {
        "repoId": normalized,
        "repoName": root.name,
        "repoPath": normalized,
        "branch": get_git_value(normalized, ["rev-parse", "--abbrev-ref", "HEAD"], "workspace"),
        "commitSha": get_git_value(normalized, ["rev-parse", "HEAD"], "unversioned"),
    }


def load_repo_config(repo_path: str) -> CostConfig:
    config_path = Path(repo_path) / ".wattwise.yml"
    raw: Dict[str, Any] = {}
    if config_path.exists():
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            raw = loaded

    cost_section = raw.get("cost", {}) if isinstance(raw.get("cost", {}), dict) else {}
    default_calls = dict(DEFAULT_CALLS_PER_DAY)
    for block_type, value in cost_section.get("default_calls_per_day", {}).items():
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            default_calls[str(block_type)] = parsed

    aws_rate = cost_section.get("aws_rate_kwh", AWS_RATE_KWH)
    co2_rate = cost_section.get("co2_kg_per_kwh", CO2_KG_PER_KWH)
    try:
        aws_rate = float(aws_rate)
    except (TypeError, ValueError):
        aws_rate = AWS_RATE_KWH
    try:
        co2_rate = float(co2_rate)
    except (TypeError, ValueError):
        co2_rate = CO2_KG_PER_KWH

    return CostConfig(
        awsRateKwh=aws_rate if aws_rate > 0 else AWS_RATE_KWH,
        co2KgPerKwh=co2_rate if co2_rate > 0 else CO2_KG_PER_KWH,
        defaultCallsPerDay=default_calls,
    )


def save_repo_config(repo_path: str, config: Dict[str, Any] | CostConfig) -> CostConfig:
    normalized = ensure_cost_config(config)
    config_path = Path(repo_path) / ".wattwise.yml"
    raw: Dict[str, Any] = {}
    if config_path.exists():
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            raw = loaded

    raw["cost"] = {
        "aws_rate_kwh": float(normalized.awsRateKwh),
        "co2_kg_per_kwh": float(normalized.co2KgPerKwh),
        "default_calls_per_day": {
            block_type: int(normalized.defaultCallsPerDay.get(block_type, DEFAULT_CALLS_PER_DAY[block_type]))
            for block_type in DEFAULT_CALLS_PER_DAY
        },
    }
    config_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return normalized


def ensure_cost_config(config: Dict[str, Any] | CostConfig | None) -> CostConfig:
    if isinstance(config, CostConfig):
        default_calls = {
            block_type: int(config.defaultCallsPerDay.get(block_type, default_value))
            for block_type, default_value in DEFAULT_CALLS_PER_DAY.items()
        }
        return CostConfig(
            awsRateKwh=float(config.awsRateKwh or AWS_RATE_KWH),
            co2KgPerKwh=float(config.co2KgPerKwh or CO2_KG_PER_KWH),
            defaultCallsPerDay=default_calls,
        )

    config = config or {}
    default_calls_payload = config.get("defaultCallsPerDay", {}) if isinstance(config, dict) else {}
    default_calls = {}
    for block_type, default_value in DEFAULT_CALLS_PER_DAY.items():
        try:
            candidate = int(default_calls_payload.get(block_type, default_value))
        except (TypeError, ValueError):
            candidate = default_value
        default_calls[block_type] = candidate if candidate > 0 else default_value

    try:
        aws_rate = float(config.get("awsRateKwh", AWS_RATE_KWH))
    except (TypeError, ValueError):
        aws_rate = AWS_RATE_KWH
    try:
        co2_rate = float(config.get("co2KgPerKwh", CO2_KG_PER_KWH))
    except (TypeError, ValueError):
        co2_rate = CO2_KG_PER_KWH

    return CostConfig(
        awsRateKwh=aws_rate if aws_rate > 0 else AWS_RATE_KWH,
        co2KgPerKwh=co2_rate if co2_rate > 0 else CO2_KG_PER_KWH,
        defaultCallsPerDay=default_calls,
    )


def should_ignore_file(repo_path: str, file_path: Path) -> bool:
    relative_parts = file_path.resolve().relative_to(Path(repo_path).resolve()).parts
    return any(part in IGNORED_SEGMENTS for part in relative_parts)


def discover_python_files(repo_path: str) -> List[Path]:
    root = Path(repo_path).resolve()
    files = [file_path for file_path in root.rglob("*.py") if file_path.is_file() and not should_ignore_file(repo_path, file_path)]
    return sorted(files)


def format_driver_value(value: float) -> str:
    if value >= 1000:
        return f"{value:.0f}"
    if value >= 10:
        return f"{value:.1f}"
    if value >= 1:
        return f"{value:.2f}"
    return f"{value:.3f}"


def get_feature_drivers(features: Dict[str, float]) -> List[FeatureDriver]:
    drivers: List[FeatureDriver] = []
    for meta in DRIVER_META:
        raw_value = float(features.get(meta["key"], 0.0))
        score = math.log10(raw_value + 1) * meta["weight"] if raw_value > 0 else 0
        if raw_value >= meta["minimum"] and score > 0.25:
            drivers.append(
                FeatureDriver(
                    key=meta["key"],
                    label=meta["label"],
                    value=raw_value,
                    displayValue=format_driver_value(raw_value),
                )
            )

    return sorted(
        drivers,
        key=lambda driver: next(item["weight"] for item in DRIVER_META if item["key"] == driver.key) * math.log10(driver.value + 1),
        reverse=True,
    )[:3]


def get_optimization_strategy(block_type: str, features: Dict[str, float], feature_drivers: List[FeatureDriver]) -> List[str]:
    suggestions: List[str] = []
    driver_keys = {driver.key for driver in feature_drivers}

    def add(text: str) -> None:
        if text not in suggestions:
            suggestions.append(text)

    if block_type == "FunctionDef":
        add("Break this function into smaller hot paths and move repeated work into shared helpers.")
        add("Cache expensive intermediate values when the function is called frequently.")
    elif block_type in {"For", "While"}:
        add("Reduce per-iteration work by hoisting invariant computations outside the loop.")
        add("Prefer built-ins, batching, or vectorized operations over Python-level iteration when possible.")
    elif block_type == "If":
        add("Flatten branching and return early so the hot path does less conditional work.")
    elif block_type == "Try":
        add("Keep the try scope narrow and move normal-path work outside exception handling.")
    elif block_type == "With":
        add("Minimize work inside the context manager and batch I/O before or after the managed block.")
    else:
        add("Reduce repeated work in this block and simplify the control flow on the hot path.")

    if features.get("feature_nesting_complexity", 0) >= 2 or "feature_nesting_complexity" in driver_keys:
        add("Flatten nested loops and conditionals to cut interpreter overhead and reduce branch churn.")
    if features.get("feature_call_density", 0) >= 0.12 or "feature_call_density" in driver_keys:
        add("Memoize or precompute repeated function calls if the inputs are stable across executions.")
    if features.get("feature_total_nodes", 0) >= 40 or "feature_total_nodes" in driver_keys:
        add("Split large mixed-responsibility blocks into smaller units so the hot path does less work.")
    if features.get("feature_cyclomatic_complexity", 0) >= 4 or "feature_cyclomatic_complexity" in driver_keys:
        add("Consolidate duplicated branches and move expensive checks behind cheaper guards.")

    return suggestions[:3]


def get_snippet(code_lines: List[str], start_line: int, end_line: int) -> str:
    return "\n".join(code_lines[max(0, start_line - 1): min(len(code_lines), end_line)]).rstrip()


def get_block_label(block_type: str, code_snippet: str) -> str:
    first_line = (code_snippet.splitlines() or [""])[0].strip()
    if block_type == "FunctionDef" and first_line.startswith("def "):
        name = first_line[4:].split("(", 1)[0].strip()
        if name:
            return f"{name}()"
    return {
        "For": "for loop",
        "While": "while loop",
        "If": "if branch",
        "Try": "try block",
        "With": "with block",
    }.get(block_type, first_line or block_type)


def get_aggregate_tier(high_count: int, medium_count: int, total_blocks: int) -> str:
    if total_blocks == 0:
        return "Low"
    high_ratio = high_count / total_blocks
    medium_ratio = medium_count / total_blocks
    if high_ratio >= 0.45:
        return "High"
    if high_ratio > 0 or medium_ratio >= 0.35:
        return "Medium"
    return "Low"


def build_block_result(
    file_path: str,
    absolute_path: str,
    code_lines: List[str],
    block: Dict[str, Any],
    prediction: Dict[str, Any],
    config: CostConfig,
) -> BlockResult | None:
    if prediction.get("error") or prediction.get("energy_joules") is None:
        return None

    energy_joules = float(prediction["energy_joules"])
    block_type = str(block["block_type"])
    calls_per_day = int(config.defaultCallsPerDay.get(block_type, DEFAULT_CALLS_PER_DAY["FunctionDef"]))
    annual_energy_kwh = annual_kwh(energy_joules, calls_per_day)
    cost_per_year = annual_cost_usd(energy_joules, calls_per_day, config.awsRateKwh)
    co2_kg_per_year = annual_co2_kg(energy_joules, calls_per_day, config.co2KgPerKwh)
    code_snippet = get_snippet(code_lines, int(block["start_line"]), int(block["end_line"]))
    features = {str(key): float(value) for key, value in (block.get("features") or {}).items()}
    feature_drivers = get_feature_drivers(features)

    return BlockResult(
        id=f"{file_path}:{block['start_line']}-{block['end_line']}:{block_type}",
        absolutePath=absolute_path,
        filePath=file_path,
        fileName=Path(file_path).name,
        modulePath=str(Path(file_path).parent).replace("\\", "/") if "/" in file_path else ".",
        label=get_block_label(block_type, code_snippet),
        blockType=block_type,
        startLine=int(block["start_line"]),
        endLine=int(block["end_line"]),
        loc=max(1, int(block["end_line"]) - int(block["start_line"]) + 1),
        energyJoules=energy_joules,
        energyTier=str(prediction.get("energy_tier", "Unknown")),
        tierConfidence=float(prediction.get("tier_confidence", 0)),
        energyFormatted=str(prediction.get("energy_formatted", f"{energy_joules:.6f}J")),
        callsPerDay=calls_per_day,
        annualKwh=annual_energy_kwh,
        costPerYear=cost_per_year,
        co2KgPerYear=co2_kg_per_year,
        codeSnippet=code_snippet,
        features=features,
        featureDrivers=feature_drivers,
        optimizationStrategy=get_optimization_strategy(block_type, features, feature_drivers),
    )


def build_file_result(
    repo_path: str,
    absolute_path: Path,
    code: str,
    blocks: List[Dict[str, Any]],
    predictions: List[Dict[str, Any]],
    config: CostConfig,
) -> FileResult:
    relative_path = normalize_relative_path(repo_path, str(absolute_path))
    code_lines = code.splitlines()
    file_blocks: List[BlockResult] = []

    for block, prediction in zip(blocks, predictions):
        result = build_block_result(relative_path, str(absolute_path), code_lines, block, prediction, config)
        if result:
            file_blocks.append(result)

    file_blocks.sort(key=lambda block: (block.costPerYear, block.energyJoules), reverse=True)
    high_count = sum(1 for block in file_blocks if block.energyTier == "High")
    medium_count = sum(1 for block in file_blocks if block.energyTier == "Medium")
    low_count = sum(1 for block in file_blocks if block.energyTier == "Low")
    total_blocks = len(file_blocks)

    return FileResult(
        absolutePath=str(absolute_path),
        path=relative_path,
        name=absolute_path.name,
        directory=str(Path(relative_path).parent).replace("\\", "/") if "/" in relative_path else "",
        loc=count_loc(code),
        totalBlocks=total_blocks,
        highCount=high_count,
        mediumCount=medium_count,
        lowCount=low_count,
        aggregateScore=(high_count / total_blocks) if total_blocks else 0.0,
        aggregateTier=get_aggregate_tier(high_count, medium_count, total_blocks),  # type: ignore[arg-type]
        totalEnergyJoules=sum(block.energyJoules for block in file_blocks),
        totalKwh=sum(block.annualKwh for block in file_blocks),
        totalCostUsd=sum(block.costPerYear for block in file_blocks),
        totalCo2Kg=sum(block.co2KgPerYear for block in file_blocks),
        blocks=file_blocks,
    )


def build_tree(files: List[FileResult], repo_name: str) -> TreeNode:
    root = TreeNode(
        kind="directory",
        name=repo_name,
        path="",
        loc=0,
        totalBlocks=0,
        highCount=0,
        aggregateScore=0,
        aggregateTier="Low",
        children=[],
    )

    def find_child(node: TreeNode, name: str) -> TreeNode | None:
        for child in node.children:
            if child.kind == "directory" and child.name == name:
                return child
        return None

    for file_result in files:
        segments = file_result.path.split("/")
        current = root
        current_path = ""
        for index, segment in enumerate(segments):
            is_file = index == len(segments) - 1
            current_path = f"{current_path}/{segment}".strip("/")
            if is_file:
                current.children.append(
                    TreeNode(
                        kind="file",
                        name=file_result.name,
                        path=file_result.path,
                        loc=file_result.loc,
                        totalBlocks=file_result.totalBlocks,
                        highCount=file_result.highCount,
                        aggregateScore=file_result.aggregateScore,
                        aggregateTier=file_result.aggregateTier,
                        children=[],
                    )
                )
                continue

            next_node = find_child(current, segment)
            if not next_node:
                next_node = TreeNode(
                    kind="directory",
                    name=segment,
                    path=current_path,
                    loc=0,
                    totalBlocks=0,
                    highCount=0,
                    aggregateScore=0,
                    aggregateTier="Low",
                    children=[],
                )
                current.children.append(next_node)
            current = next_node

    def aggregate(node: TreeNode) -> TreeNode:
        if node.kind == "file":
            return node
        node.children = [aggregate(child) for child in node.children]
        node.children.sort(key=lambda child: child.name.lower())
        node.loc = sum(child.loc for child in node.children)
        node.totalBlocks = sum(child.totalBlocks for child in node.children)
        node.highCount = sum(child.highCount for child in node.children)
        node.aggregateScore = (node.highCount / node.totalBlocks) if node.totalBlocks else 0.0
        if node.aggregateScore >= 0.45:
            node.aggregateTier = "High"
        elif node.aggregateScore > 0:
            node.aggregateTier = "Medium"
        else:
            node.aggregateTier = "Low"
        return node

    return aggregate(root)


def build_scan_result(
    scan_id: str,
    repo_meta: Dict[str, str],
    config: CostConfig,
    files: List[FileResult],
    history: List[HistoryPoint],
) -> ScanResult:
    sorted_files = sorted(files, key=lambda file_result: (file_result.loc, file_result.totalCostUsd), reverse=True)
    hotspots = sorted(
        [block for file_result in sorted_files for block in file_result.blocks],
        key=lambda block: (block.costPerYear, block.energyJoules),
        reverse=True,
    )
    total_blocks = sum(file_result.totalBlocks for file_result in sorted_files)
    total_high = sum(file_result.highCount for file_result in sorted_files)
    total_medium = sum(file_result.mediumCount for file_result in sorted_files)
    total_low = sum(file_result.lowCount for file_result in sorted_files)
    total_loc = sum(file_result.loc for file_result in sorted_files)
    total_cost = sum(file_result.totalCostUsd for file_result in sorted_files)
    total_kwh = sum(file_result.totalKwh for file_result in sorted_files)
    total_co2 = sum(file_result.totalCo2Kg for file_result in sorted_files)
    scanned_at = history[-1].scannedAt if history else ""

    return ScanResult(
        scanId=scan_id,
        repoId=repo_meta["repoId"],
        repoName=repo_meta["repoName"],
        repoPath=repo_meta["repoPath"],
        branch=repo_meta["branch"],
        commitSha=repo_meta["commitSha"],
        scannedAt=scanned_at,
        fileCount=len(sorted_files),
        totalLoc=total_loc,
        totalBlocks=total_blocks,
        totalHigh=total_high,
        totalMedium=total_medium,
        totalLow=total_low,
        totalCostUsd=total_cost,
        totalKwh=total_kwh,
        totalCo2Kg=total_co2,
        potentialSavingUsd=sum(block.costPerYear for block in hotspots[:5]),
        energyDebtScore=round((total_high / total_blocks) * 100) if total_blocks else 0,
        files=sorted_files,
        hotspots=hotspots,
        tree=build_tree(sorted_files, repo_meta["repoName"]),
        history=history,
        config=config,
    )


class RepositoryScanner:
    def __init__(self, bridge: WattWiseBridge | None = None) -> None:
        self.bridge = bridge or WattWiseBridge()

    def scan_repository(
        self,
        scan_id: str,
        repo_path: str,
        history: List[HistoryPoint] | None = None,
        progress_callback: Callable[[Dict[str, Any]], None] | None = None,
    ) -> ScanResult:
        normalized_repo_path = normalize_repo_path(repo_path)
        root = Path(normalized_repo_path)
        if not root.exists() or not root.is_dir():
            raise FileNotFoundError(f"Repository path does not exist: {normalized_repo_path}")

        config = load_repo_config(normalized_repo_path)
        repo_meta = get_repo_meta(normalized_repo_path)
        files = discover_python_files(normalized_repo_path)
        total_files = len(files)
        current_history = history or []

        if progress_callback:
            progress_callback({
                "message": f"Found {total_files} Python files",
                "scannedFiles": 0,
                "totalFiles": total_files,
            })

        file_results: List[FileResult] = []
        for index, file_path in enumerate(files, start=1):
            relative_path = normalize_relative_path(normalized_repo_path, str(file_path))
            if progress_callback:
                progress_callback({
                    "message": f"Scanning {relative_path}",
                    "scannedFiles": index - 1,
                    "totalFiles": total_files,
                })

            try:
                code = file_path.read_text(encoding="utf-8", errors="ignore")
                if not code.strip():
                    file_results.append(build_file_result(normalized_repo_path, file_path, code, [], [], config))
                    partial_result = build_scan_result(scan_id, repo_meta, config, file_results, list(current_history))
                    if progress_callback:
                        progress_callback({
                            "message": f"Indexed {relative_path} (no analysable blocks)",
                            "scannedFiles": index,
                            "totalFiles": total_files,
                            "snapshot": partial_result.to_dict(),
                        })
                    continue

                blocks = self.bridge.extract_features_from_file(str(file_path))
                if not blocks:
                    file_results.append(build_file_result(normalized_repo_path, file_path, code, [], [], config))
                    partial_result = build_scan_result(scan_id, repo_meta, config, file_results, list(current_history))
                    if progress_callback:
                        progress_callback({
                            "message": f"Indexed {relative_path} (no analysable blocks)",
                            "scannedFiles": index,
                            "totalFiles": total_files,
                            "snapshot": partial_result.to_dict(),
                        })
                    continue

                predictions = self.bridge.predict_energy(blocks)
                file_result = build_file_result(normalized_repo_path, file_path, code, blocks, predictions, config)
                file_results.append(file_result)
                partial_result = build_scan_result(scan_id, repo_meta, config, file_results, list(current_history))
                if progress_callback:
                    progress_callback({
                        "message": f"Scanned {relative_path}",
                        "scannedFiles": index,
                        "totalFiles": total_files,
                        "snapshot": partial_result.to_dict(),
                    })
            except Exception as exc:
                try:
                    fallback_code = file_path.read_text(encoding="utf-8", errors="ignore")
                    file_results.append(build_file_result(normalized_repo_path, file_path, fallback_code, [], [], config))
                except Exception:
                    pass
                if progress_callback:
                    partial_result = build_scan_result(scan_id, repo_meta, config, file_results, list(current_history))
                    progress_callback({
                        "message": f"Indexed {relative_path} with no block data: {exc}",
                        "scannedFiles": index,
                        "totalFiles": total_files,
                        "snapshot": partial_result.to_dict(),
                    })
                continue

        final_scanned_at = current_timestamp()
        next_point = HistoryPoint(
            date=final_scanned_at[:10],
            scannedAt=final_scanned_at,
            commitSha=repo_meta["commitSha"],
            energyDebtScore=0,
            costUsd=0.0,
        )
        next_history = list(current_history) + [next_point]
        next_history = next_history[-24:]

        result = build_scan_result(scan_id, repo_meta, config, file_results, next_history)
        result.scannedAt = final_scanned_at
        result.history[-1].energyDebtScore = result.energyDebtScore
        result.history[-1].costUsd = result.totalCostUsd
        result.history[-1].scannedAt = final_scanned_at
        result.history[-1].date = final_scanned_at[:10]
        return result


def current_timestamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def recalculate_scan_payload(scan_data: Dict[str, Any], config_payload: Dict[str, Any] | CostConfig) -> Dict[str, Any]:
    data = deepcopy(scan_data)
    config = ensure_cost_config(config_payload)
    files = data.get("files", [])

    for file_result in files:
        for block in file_result.get("blocks", []):
            calls_per_day = int(config.defaultCallsPerDay.get(block["blockType"], DEFAULT_CALLS_PER_DAY["FunctionDef"]))
            block["callsPerDay"] = calls_per_day
            block["annualKwh"] = annual_kwh(float(block["energyJoules"]), calls_per_day)
            block["costPerYear"] = annual_cost_usd(float(block["energyJoules"]), calls_per_day, config.awsRateKwh)
            block["co2KgPerYear"] = annual_co2_kg(float(block["energyJoules"]), calls_per_day, config.co2KgPerKwh)

        file_result["blocks"].sort(key=lambda item: (item["costPerYear"], item["energyJoules"]), reverse=True)
        file_result["totalKwh"] = sum(block["annualKwh"] for block in file_result["blocks"])
        file_result["totalCostUsd"] = sum(block["costPerYear"] for block in file_result["blocks"])
        file_result["totalCo2Kg"] = sum(block["co2KgPerYear"] for block in file_result["blocks"])
        file_result["totalEnergyJoules"] = sum(block["energyJoules"] for block in file_result["blocks"])

    files.sort(key=lambda item: (item["loc"], item["totalCostUsd"]), reverse=True)
    hotspots = [block for file_result in files for block in file_result["blocks"]]
    hotspots.sort(key=lambda item: (item["costPerYear"], item["energyJoules"]), reverse=True)

    data["files"] = files
    data["hotspots"] = hotspots
    data["fileCount"] = len(files)
    data["totalLoc"] = sum(file_result["loc"] for file_result in files)
    data["totalBlocks"] = sum(file_result["totalBlocks"] for file_result in files)
    data["totalHigh"] = sum(file_result["highCount"] for file_result in files)
    data["totalMedium"] = sum(file_result["mediumCount"] for file_result in files)
    data["totalLow"] = sum(file_result["lowCount"] for file_result in files)
    data["totalCostUsd"] = sum(file_result["totalCostUsd"] for file_result in files)
    data["totalKwh"] = sum(file_result["totalKwh"] for file_result in files)
    data["totalCo2Kg"] = sum(file_result["totalCo2Kg"] for file_result in files)
    data["potentialSavingUsd"] = sum(block["costPerYear"] for block in hotspots[:5])
    data["energyDebtScore"] = round((data["totalHigh"] / data["totalBlocks"]) * 100) if data["totalBlocks"] else 0
    data["config"] = config.to_dict()
    data["tree"] = build_tree(
        [
            FileResult(
                absolutePath=file_result["absolutePath"],
                path=file_result["path"],
                name=file_result["name"],
                directory=file_result["directory"],
                loc=file_result["loc"],
                totalBlocks=file_result["totalBlocks"],
                highCount=file_result["highCount"],
                mediumCount=file_result["mediumCount"],
                lowCount=file_result["lowCount"],
                aggregateScore=file_result["aggregateScore"],
                aggregateTier=file_result["aggregateTier"],
                totalEnergyJoules=file_result["totalEnergyJoules"],
                totalKwh=file_result["totalKwh"],
                totalCostUsd=file_result["totalCostUsd"],
                totalCo2Kg=file_result["totalCo2Kg"],
                blocks=[],
            )
            for file_result in files
        ],
        data["repoName"],
    ).to_dict()
    return data


def build_csv(scan_data: Dict[str, Any]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "file_path",
        "block_type",
        "label",
        "start_line",
        "end_line",
        "tier",
        "confidence",
        "energy_joules",
        "calls_per_day",
        "annual_kwh",
        "cost_per_year_usd",
        "co2_kg_per_year",
        "feature_drivers",
    ])

    for block in scan_data.get("hotspots", []):
        writer.writerow([
            block["filePath"],
            block["blockType"],
            block["label"],
            block["startLine"],
            block["endLine"],
            block["energyTier"],
            f"{float(block['tierConfidence']):.4f}",
            f"{float(block['energyJoules']):.8f}",
            block["callsPerDay"],
            f"{float(block['annualKwh']):.8f}",
            f"{float(block['costPerYear']):.8f}",
            f"{float(block['co2KgPerYear']):.8f}",
            "; ".join(f"{driver['label']}={driver['displayValue']}" for driver in block.get("featureDrivers", [])),
        ])

    return output.getvalue()
