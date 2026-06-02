from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List


class Database:
    def __init__(self, db_path: str | None = None) -> None:
        default_path = Path(__file__).resolve().parents[1] / "data" / "wattwise_dashboard.db"
        self.db_path = Path(db_path or default_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        return connection

    def init(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS scans (
                    id INTEGER PRIMARY KEY,
                    scan_key TEXT UNIQUE,
                    repo_id TEXT,
                    repo_path TEXT,
                    repo_name TEXT,
                    commit_sha TEXT,
                    branch TEXT,
                    scanned_at TEXT,
                    total_high INTEGER,
                    total_medium INTEGER,
                    total_low INTEGER,
                    total_cost_usd REAL,
                    total_kwh REAL,
                    total_co2_kg REAL,
                    potential_saving_usd REAL,
                    energy_debt_score INTEGER,
                    payload_json TEXT
                );

                CREATE TABLE IF NOT EXISTS block_results (
                    id INTEGER PRIMARY KEY,
                    scan_key TEXT REFERENCES scans(scan_key),
                    file_path TEXT,
                    absolute_path TEXT,
                    file_name TEXT,
                    module_path TEXT,
                    label TEXT,
                    block_type TEXT,
                    start_line INTEGER,
                    end_line INTEGER,
                    loc INTEGER,
                    energy_j REAL,
                    tier TEXT,
                    confidence REAL,
                    calls_per_day INTEGER,
                    annual_kwh REAL,
                    cost_per_year REAL,
                    co2_kg_per_year REAL,
                    code_snippet TEXT,
                    features_json TEXT,
                    feature_drivers_json TEXT,
                    optimization_json TEXT
                );
                """
            )

    def save_scan(self, scan_data: Dict[str, Any]) -> None:
        payload_json = json.dumps(scan_data)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO scans (
                    scan_key, repo_id, repo_path, repo_name, commit_sha, branch, scanned_at,
                    total_high, total_medium, total_low, total_cost_usd, total_kwh, total_co2_kg,
                    potential_saving_usd, energy_debt_score, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scan_key) DO UPDATE SET
                    repo_id=excluded.repo_id,
                    repo_path=excluded.repo_path,
                    repo_name=excluded.repo_name,
                    commit_sha=excluded.commit_sha,
                    branch=excluded.branch,
                    scanned_at=excluded.scanned_at,
                    total_high=excluded.total_high,
                    total_medium=excluded.total_medium,
                    total_low=excluded.total_low,
                    total_cost_usd=excluded.total_cost_usd,
                    total_kwh=excluded.total_kwh,
                    total_co2_kg=excluded.total_co2_kg,
                    potential_saving_usd=excluded.potential_saving_usd,
                    energy_debt_score=excluded.energy_debt_score,
                    payload_json=excluded.payload_json
                """,
                (
                    scan_data["scanId"],
                    scan_data["repoId"],
                    scan_data["repoPath"],
                    scan_data["repoName"],
                    scan_data["commitSha"],
                    scan_data["branch"],
                    scan_data["scannedAt"],
                    scan_data["totalHigh"],
                    scan_data["totalMedium"],
                    scan_data["totalLow"],
                    scan_data["totalCostUsd"],
                    scan_data["totalKwh"],
                    scan_data["totalCo2Kg"],
                    scan_data["potentialSavingUsd"],
                    scan_data["energyDebtScore"],
                    payload_json,
                ),
            )
            connection.execute("DELETE FROM block_results WHERE scan_key = ?", (scan_data["scanId"],))
            for block in scan_data.get("hotspots", []):
                connection.execute(
                    """
                    INSERT INTO block_results (
                        scan_key, file_path, absolute_path, file_name, module_path, label, block_type,
                        start_line, end_line, loc, energy_j, tier, confidence, calls_per_day, annual_kwh,
                        cost_per_year, co2_kg_per_year, code_snippet, features_json, feature_drivers_json, optimization_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        scan_data["scanId"],
                        block["filePath"],
                        block["absolutePath"],
                        block["fileName"],
                        block["modulePath"],
                        block["label"],
                        block["blockType"],
                        block["startLine"],
                        block["endLine"],
                        block["loc"],
                        block["energyJoules"],
                        block["energyTier"],
                        block["tierConfidence"],
                        block["callsPerDay"],
                        block["annualKwh"],
                        block["costPerYear"],
                        block["co2KgPerYear"],
                        block["codeSnippet"],
                        json.dumps(block.get("features", {})),
                        json.dumps(block.get("featureDrivers", [])),
                        json.dumps(block.get("optimizationStrategy", [])),
                    ),
                )

    def get_scan(self, scan_key: str) -> Dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM scans WHERE scan_key = ?",
                (scan_key,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["payload_json"])

    def get_latest_scan(self, repo_id: str) -> Dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM scans WHERE repo_id = ? ORDER BY scanned_at DESC LIMIT 1",
                (repo_id,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["payload_json"])

    def get_history(self, repo_id: str) -> List[Dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT scanned_at, commit_sha, energy_debt_score, total_cost_usd
                FROM (
                    SELECT scanned_at, commit_sha, energy_debt_score, total_cost_usd
                    FROM scans
                    WHERE repo_id = ?
                    ORDER BY scanned_at DESC
                    LIMIT 24
                )
                ORDER BY scanned_at ASC
                """,
                (repo_id,),
            ).fetchall()
        return [
            {
                "date": row["scanned_at"][:10],
                "scannedAt": row["scanned_at"],
                "commitSha": row["commit_sha"],
                "energyDebtScore": row["energy_debt_score"],
                "costUsd": row["total_cost_usd"],
            }
            for row in rows
        ]

    def get_hotspots(
        self,
        scan_key: str,
        sort_by: str = "cost",
        limit: int = 50,
        file_path: str | None = None,
        module_path: str | None = None,
    ) -> List[Dict[str, Any]]:
        order_by = {
            "cost": "cost_per_year DESC, energy_j DESC",
            "tier": "CASE tier WHEN 'High' THEN 3 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 1 ELSE 0 END DESC, cost_per_year DESC",
            "loc": "loc DESC, cost_per_year DESC",
            "type": "block_type ASC, cost_per_year DESC",
        }.get(sort_by, "cost_per_year DESC, energy_j DESC")

        clauses = ["scan_key = ?"]
        params: List[Any] = [scan_key]
        if file_path:
            clauses.append("file_path = ?")
            params.append(file_path)
        if module_path:
            clauses.append("module_path = ?")
            params.append(module_path)
        params.append(limit)

        query = f"""
            SELECT *
            FROM block_results
            WHERE {' AND '.join(clauses)}
            ORDER BY {order_by}
            LIMIT ?
        """
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._block_row_to_dict(row) for row in rows]

    def get_file_blocks(self, scan_key: str, file_path: str) -> List[Dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM block_results
                WHERE scan_key = ? AND file_path = ?
                ORDER BY start_line ASC
                """,
                (scan_key, file_path),
            ).fetchall()
        return [self._block_row_to_dict(row) for row in rows]

    def _block_row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": f"{row['file_path']}:{row['start_line']}-{row['end_line']}:{row['block_type']}",
            "absolutePath": row["absolute_path"],
            "filePath": row["file_path"],
            "fileName": row["file_name"],
            "modulePath": row["module_path"],
            "label": row["label"],
            "blockType": row["block_type"],
            "startLine": row["start_line"],
            "endLine": row["end_line"],
            "loc": row["loc"],
            "energyJoules": row["energy_j"],
            "energyTier": row["tier"],
            "tierConfidence": row["confidence"],
            "callsPerDay": row["calls_per_day"],
            "annualKwh": row["annual_kwh"],
            "costPerYear": row["cost_per_year"],
            "co2KgPerYear": row["co2_kg_per_year"],
            "codeSnippet": row["code_snippet"],
            "features": json.loads(row["features_json"] or "{}"),
            "featureDrivers": json.loads(row["feature_drivers_json"] or "[]"),
            "optimizationStrategy": json.loads(row["optimization_json"] or "[]"),
        }
