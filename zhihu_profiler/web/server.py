"""Web API server for Zhihu Profiler."""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel

from ..scraper.zhihu import ZhihuScraper
from ..scraper.models import ScrapedData
from ..analysis.profiler import Profiler, UserProfile
from ..viz.dashboard import ReportGenerator

logger = logging.getLogger(__name__)

# Storage
STORAGE_DIR = Path(__file__).parent.parent.parent / ".analyses"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# In-memory job tracking
jobs: dict[str, dict] = {}

app = FastAPI(title="Zhihu Profiler", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    url: str
    max_answers: int = 200


class JobStatus(BaseModel):
    id: str
    status: str
    progress: int = 0
    message: str = ""
    user_name: str = ""
    created_at: str = ""
    completed_at: str = ""


async def run_analysis(job_id: str, user_url: str, max_answers: int):
    """Run full analysis pipeline in background."""
    job = jobs[job_id]
    try:
        # Phase 1: Scraping
        job["status"] = "scraping"
        job["message"] = "正在抓取知乎数据..."
        job["progress"] = 10

        async with ZhihuScraper(headless=True, max_answers=max_answers) as scraper:
            data = await scraper.scrape_user(user_url)

        job["progress"] = 40
        job["message"] = f"已抓取 {data.answers_scraped} 条回答"
        job["user_name"] = data.user.name

        # Phase 2: Analysis
        job["status"] = "analyzing"
        job["message"] = "正在分析人格特征..."
        job["progress"] = 50

        profiler = Profiler()
        profile = profiler.profile(data)

        job["progress"] = 80
        job["message"] = "正在生成报告..."

        # Phase 3: Generate report
        report_dir = STORAGE_DIR / job_id
        report_dir.mkdir(parents=True, exist_ok=True)

        generator = ReportGenerator(output_dir=report_dir)
        report_path = generator.generate(profile)
        job["report_path"] = str(report_path)

        # Save JSON profile
        json_path = report_dir / "profile.json"
        profiler.save_profile(profile, json_path)

        # Save raw data
        raw_path = report_dir / "raw.json"
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(data.model_dump_json(indent=2, ensure_ascii=False))

        job["status"] = "completed"
        job["progress"] = 100
        job["message"] = "分析完成"
        job["completed_at"] = datetime.now().isoformat()
        job["profile"] = {
            "name": profile.user.get("name", "") if profile.user else "",
            "answers": profile.total_answers,
            "chars": profile.total_chars,
            "upvotes": profile.total_upvotes,
            "summary": profile.summary,
        }

    except Exception as e:
        logger.error(f"Analysis failed: {traceback.format_exc()}")
        job["status"] = "failed"
        job["message"] = str(e)


@app.post("/api/analyze")
async def start_analysis(req: AnalyzeRequest):
    """Start a new analysis job."""
    job_id = str(uuid.uuid4())[:8]

    jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "progress": 0,
        "message": "排队中...",
        "user_name": "",
        "created_at": datetime.now().isoformat(),
        "completed_at": "",
    }

    # Run in background
    asyncio.create_task(run_analysis(job_id, req.url, req.max_answers))

    return {"job_id": job_id, "status": "queued"}


@app.get("/api/analyze/{job_id}")
async def get_job_status(job_id: str):
    """Get analysis job status."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    return JobStatus(
        id=job["id"],
        status=job["status"],
        progress=job.get("progress", 0),
        message=job.get("message", ""),
        user_name=job.get("user_name", ""),
        created_at=job.get("created_at", ""),
        completed_at=job.get("completed_at", ""),
    )


@app.get("/api/analyze/{job_id}/report")
async def get_report(job_id: str):
    """Get the HTML report for a completed analysis."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Analysis not completed")

    report_path = job.get("report_path", "")
    if not report_path or not Path(report_path).exists():
        raise HTTPException(status_code=404, detail="Report file not found")

    return FileResponse(report_path)


@app.get("/api/history")
async def get_history():
    """Get analysis history from storage."""
    history = []
    for job_dir in sorted(STORAGE_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not job_dir.is_dir():
            continue

        json_path = job_dir / "profile.json"
        report_path = job_dir / f"{job_dir.name}*"
        reports = list(job_dir.glob("*.html"))

        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    profile = json.load(f)

                history.append({
                    "id": job_dir.name,
                    "name": profile.get("user", {}).get("name", "Unknown"),
                    "answers": profile.get("total_answers", 0),
                    "date": datetime.fromtimestamp(job_dir.stat().st_mtime).isoformat(),
                    "has_report": len(reports) > 0,
                    "avatar": profile.get("user", {}).get("avatar_url", ""),
                })
            except Exception:
                continue

    return history[:20]


@app.delete("/api/history/{analysis_id}")
async def delete_analysis(analysis_id: str):
    """Delete a saved analysis."""
    job_dir = STORAGE_DIR / analysis_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Analysis not found")

    import shutil
    shutil.rmtree(job_dir)

    # Remove from jobs if present
    if analysis_id in jobs:
        del jobs[analysis_id]

    return {"ok": True}


@app.get("/api/analyze/{job_id}/profile")
async def get_profile(job_id: str):
    """Get structured profile data."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Analysis not completed")

    return job.get("profile", {})


# Serve static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Read index HTML at startup for fast serving
_index_html: str = ""
_index_path = static_dir / "index.html"
if _index_path.exists():
    _index_html = _index_path.read_text(encoding="utf-8")


@app.get("/")
async def index():
    """Serve the main page."""
    if _index_html:
        return HTMLResponse(_index_html)
    return FileResponse(str(static_dir / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
