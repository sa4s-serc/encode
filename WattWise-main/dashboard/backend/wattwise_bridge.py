from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


class WattWiseBridge:
    def __init__(self, python_executable: str | None = None) -> None:
        self.project_root = Path(__file__).resolve().parents[2]
        self.python_root = self.project_root / "python"
        self.extract_script = self.python_root / "extract_features.py"
        self.predict_script = self.python_root / "predict_energy.py"
        self.models_dir = self.python_root / "models"
        self.python_executable = python_executable or os.environ.get("WATTWISE_PYTHON") or sys.executable

    def extract_features_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        process = subprocess.run(
            [self.python_executable, str(self.extract_script), file_path],
            cwd=str(self.python_root),
            capture_output=True,
            text=True,
            check=False,
        )

        if process.returncode != 0:
            raise RuntimeError(process.stderr.strip() or "Feature extraction failed.")

        payload = json.loads(process.stdout or "[]")
        if isinstance(payload, dict) and payload.get("error"):
            raise RuntimeError(payload["error"])
        if not isinstance(payload, list):
            raise RuntimeError("Unexpected feature extraction payload.")
        return payload

    def predict_energy(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self.models_dir.exists():
            raise RuntimeError("Models not found. Train or copy the ML models before scanning.")

        process = subprocess.run(
            [self.python_executable, str(self.predict_script)],
            cwd=str(self.python_root),
            input=json.dumps(blocks),
            capture_output=True,
            text=True,
            check=False,
        )

        if process.returncode != 0:
            raise RuntimeError(process.stderr.strip() or "Energy prediction failed.")

        payload = json.loads(process.stdout or "[]")
        if isinstance(payload, dict) and payload.get("error"):
            raise RuntimeError(payload["error"])
        if not isinstance(payload, list):
            raise RuntimeError("Unexpected prediction payload.")
        return payload
