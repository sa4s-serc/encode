from __future__ import annotations

import json
import queue
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from .db import Database
from .models import HistoryPoint
from .scanner import (
    RepositoryScanner,
    build_csv,
    ensure_cost_config,
    get_repo_meta,
    load_repo_config,
    normalize_repo_path,
    recalculate_scan_payload,
    save_repo_config,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PROJECT_ROOT / "dashboard" / "frontend"
FRONTEND_DIST_ROOT = FRONTEND_ROOT / "dist"
FRONTEND_ASSETS_ROOT = FRONTEND_DIST_ROOT / "assets"

app = FastAPI(title="WattWise Repository Dashboard")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

database = Database()
scanner = RepositoryScanner()


@dataclass
class ScanJob:
    scan_id: str
    repo_path: str
    status: str = "queued"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    events: "queue.Queue[Optional[Dict[str, Any]]]" = field(default_factory=queue.Queue)

    def emit(self, event: str, data: Dict[str, Any]) -> None:
        self.events.put({"event": event, "data": data})


jobs: Dict[str, ScanJob] = {}
jobs_lock = threading.Lock()


class ScanRequest(BaseModel):
    repoPath: str = Field(..., min_length=1)


class ConfigUpdateRequest(BaseModel):
    repoPath: str = Field(..., min_length=1)
    scanId: str | None = None
    config: Dict[str, Any]


@app.on_event("startup")
def on_startup() -> None:
    database.init()


def get_job(scan_id: str) -> ScanJob | None:
    with jobs_lock:
        return jobs.get(scan_id)


def format_sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def run_scan_job(job: ScanJob) -> None:
    try:
        job.status = "running"
        repo_id = normalize_repo_path(job.repo_path)
        history = [HistoryPoint(**point) for point in database.get_history(repo_id)]

        def on_progress(payload: Dict[str, Any]) -> None:
            job.emit("progress", payload)

        result = scanner.scan_repository(job.scan_id, job.repo_path, history=history, progress_callback=on_progress)
        result_payload = result.to_dict()
        database.save_scan(result_payload)
        job.result = result_payload
        job.status = "completed"
        job.emit("complete", {"scanId": job.scan_id, "repoId": result_payload["repoId"]})
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        job.emit("scan-error", {"message": job.error})
    finally:
        job.events.put(None)


@app.get("/")
def index() -> FileResponse:
    index_file = FRONTEND_DIST_ROOT / "index.html"
    if not index_file.exists():
        raise HTTPException(
            status_code=503,
            detail="Frontend build not found. Run `cd dashboard/frontend && npm install && npm run build`.",
        )
    return FileResponse(index_file)


@app.get("/assets/{asset_path:path}")
def frontend_assets(asset_path: str) -> FileResponse:
    asset_file = FRONTEND_ASSETS_ROOT / asset_path
    if not asset_file.exists() or not asset_file.is_file():
        raise HTTPException(status_code=404, detail="Frontend asset not found.")
    return FileResponse(asset_file)


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {"status": "ok"}


@app.get("/api/default-repo")
def default_repo() -> Dict[str, Any]:
    return {"repoPath": str(PROJECT_ROOT)}


@app.post("/api/scan")
def start_scan(request: ScanRequest) -> Dict[str, Any]:
    repo_path = normalize_repo_path(request.repoPath)
    repo_root = Path(repo_path)
    if not repo_root.exists() or not repo_root.is_dir():
        raise HTTPException(status_code=404, detail=f"Repository path not found: {repo_path}")

    scan_id = uuid.uuid4().hex
    job = ScanJob(scan_id=scan_id, repo_path=repo_path)
    with jobs_lock:
        jobs[scan_id] = job

    thread = threading.Thread(target=run_scan_job, args=(job,), daemon=True)
    thread.start()
    return {"scanId": scan_id, "repoId": repo_path, "repoMeta": get_repo_meta(repo_path)}


@app.get("/api/scans/{scan_id}")
def get_scan(scan_id: str) -> Dict[str, Any]:
    job = get_job(scan_id)
    if job and job.result:
        return job.result

    stored = database.get_scan(scan_id)
    if stored:
        return stored

    if job and job.error:
        raise HTTPException(status_code=500, detail=job.error)

    raise HTTPException(status_code=404, detail="Scan not found.")


@app.get("/api/scans/{scan_id}/events")
def stream_scan_events(scan_id: str) -> StreamingResponse:
    job = get_job(scan_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found.")

    def event_stream():
        yield "retry: 1000\n\n"
        while True:
            try:
                event = job.events.get(timeout=15)
            except queue.Empty:
                yield format_sse("ping", {})
                if job.status in {"completed", "failed"} and job.events.empty():
                    break
                continue

            if event is None:
                break

            yield format_sse(event["event"], event["data"])

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/repos/latest")
def latest_repo_scan(repo_path: str = Query(..., alias="repoPath")) -> Dict[str, Any]:
    stored = database.get_latest_scan(normalize_repo_path(repo_path))
    if not stored:
        raise HTTPException(status_code=404, detail="No scan found for this repository.")
    return stored


@app.get("/api/history")
def history(repo_path: str = Query(..., alias="repoPath")) -> Dict[str, Any]:
    return {"items": database.get_history(normalize_repo_path(repo_path))}


@app.get("/api/config")
def get_config(repo_path: str = Query(..., alias="repoPath")) -> Dict[str, Any]:
    return load_repo_config(normalize_repo_path(repo_path)).to_dict()


@app.put("/api/config")
def update_config(request: ConfigUpdateRequest) -> Dict[str, Any]:
    repo_path = normalize_repo_path(request.repoPath)
    config = save_repo_config(repo_path, request.config)

    target_scan_id = request.scanId
    current_scan = database.get_scan(target_scan_id) if target_scan_id else None
    if current_scan is None:
        current_scan = database.get_latest_scan(repo_path)

    if current_scan is None:
        return {"config": config.to_dict()}

    recalculated = recalculate_scan_payload(current_scan, config)
    database.save_scan(recalculated)

    job = get_job(recalculated["scanId"])
    if job:
        job.result = recalculated

    return recalculated


@app.get("/api/scans/{scan_id}/hotspots")
def hotspots(
    scan_id: str,
    sort: str = Query("cost"),
    limit: int = Query(50, ge=1, le=500),
    file_path: str | None = Query(None, alias="filePath"),
    module_path: str | None = Query(None, alias="modulePath"),
) -> Dict[str, Any]:
    scan_data = database.get_scan(scan_id)
    if not scan_data:
        raise HTTPException(status_code=404, detail="Scan not found.")
    return {
        "items": database.get_hotspots(scan_id, sort_by=sort, limit=limit, file_path=file_path, module_path=module_path)
    }


@app.get("/api/scans/{scan_id}/file")
def file_blocks(scan_id: str, path: str = Query(...)) -> Dict[str, Any]:
    scan_data = database.get_scan(scan_id)
    if not scan_data:
        raise HTTPException(status_code=404, detail="Scan not found.")
    files = {item["path"]: item for item in scan_data.get("files", [])}
    file_summary = files.get(path)
    if not file_summary:
        raise HTTPException(status_code=404, detail="File not found in scan.")
    file_summary["blocks"] = database.get_file_blocks(scan_id, path)
    return file_summary


@app.get("/api/scans/{scan_id}/export.csv")
def export_csv(scan_id: str) -> PlainTextResponse:
    scan_data = database.get_scan(scan_id)
    if not scan_data:
        raise HTTPException(status_code=404, detail="Scan not found.")
    return PlainTextResponse(
        build_csv(scan_data),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{scan_id}-wattwise.csv"'},
    )

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("dashboard.backend.main:app", host="127.0.0.1", port=8000, reload=False)
