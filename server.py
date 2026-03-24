"""
FastAPI server exposing crawl index, search, and status endpoints.
Serves the web UI from static/ directory.
"""

import asyncio
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from crawler.storage import Storage
from crawler.backpressure import BackPressureController
from crawler.indexer import CrawlManager
from crawler.searcher import Searcher

# ── Logging ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("server")

# ── Globals ─────────────────────────────────────────────────────
storage: Storage = None  # type: ignore
crawl_manager: CrawlManager = None  # type: ignore
searcher: Searcher = None  # type: ignore

BASE_DIR = Path(__file__).parent
PDATA_PATH = str(BASE_DIR / "data" / "storage" / "p.data")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    global storage, crawl_manager, searcher

    storage = Storage()
    await storage.initialize()

    bp = BackPressureController(max_concurrent=10, max_per_second=20.0, max_queue_depth=10000)
    crawl_manager = CrawlManager(storage, bp)
    searcher = Searcher(storage)

    # Resume any interrupted jobs
    await crawl_manager.resume_jobs()

    logger.info("Server started — crawler ready")
    yield

    logger.info("Server shutting down...")
    await crawl_manager.cleanup()
    await storage.close()
    logger.info("Server shut down")


app = FastAPI(title="Web Crawler", lifespan=lifespan)

# Allow CORS for local frontend -> remote backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serves the static folder for the frontend
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


# ── Request / Response models ──────────────────────────────────
class IndexRequest(BaseModel):
    url: str
    depth: int = 2


class SearchResult(BaseModel):
    relevant_url: str
    origin_url: str
    depth: int
    title: str = ""
    score: float = 0.0


# ── API Endpoints ──────────────────────────────────────────────

@app.post("/api/index")
async def start_index(req: IndexRequest):
    """Start a new crawl job."""
    if req.depth < 0 or req.depth > 10:
        raise HTTPException(400, "Depth must be between 0 and 10")
    if not req.url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")

    try:
        job_id = await crawl_manager.start_job(req.url, req.depth)
        return {"job_id": job_id, "status": "started", "origin": req.url, "depth": req.depth}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/search")
async def search(q: str = Query(..., min_length=1)):
    """Search indexed pages."""
    results = await searcher.search(q)
    return {"query": q, "count": len(results), "results": results}


@app.get("/search")
async def search_hw(query: str = Query(..., min_length=1), sortBy: str = "relevance"):
    """Search endpoint matching homework format: /search?query=...&sortBy=relevance"""
    results = await searcher.search_by_frequency(query)
    return {"query": query, "sortBy": sortBy, "count": len(results), "results": results}


@app.post("/api/export")
async def export_pdata():
    """Export word frequencies to data/storage/p.data file."""
    await storage.export_to_pdata(PDATA_PATH)
    return {"status": "exported", "path": PDATA_PATH}


@app.get("/api/status")
async def get_status():
    """Get system status including back pressure metrics."""
    status = await crawl_manager.get_status()
    return status


@app.get("/api/jobs")
async def get_jobs():
    """List all crawl jobs."""
    jobs = await storage.get_all_jobs()
    # Enrich with indexed page counts
    enriched = []
    for job in jobs:
        count = await storage.get_indexed_page_count(job["id"])
        queue = await storage.get_queue_depth(job["id"])
        enriched.append({**job, "indexed_pages": count, "queue_depth": queue})
    return {"jobs": enriched}


@app.post("/api/jobs/{job_id}/stop")
async def stop_job(job_id: int):
    """Stop a specific crawl job."""
    success = await crawl_manager.stop_job(job_id)
    if not success:
        # If it's not active in memory, forcefully set it in the DB to clear UI
        await storage.update_job_status(job_id, "stopped")
    return {"message": f"Job {job_id} stopping", "status": "stopped"}


# ── Main ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=3600, reload=False)
