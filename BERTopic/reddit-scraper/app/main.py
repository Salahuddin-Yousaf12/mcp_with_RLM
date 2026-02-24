"""
Reddit Scraper - Simple API
----------------------------
Just give it a query and it scrapes EVERYTHING.

GET /search?q=<query>

That's it. No parameters, no filters.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.scraper import scrape_search
from app.models import SavedResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("/data")

app = FastAPI(
    title="Reddit Scraper",
    description="Scrape ALL posts and comments from Reddit search. Just the query.",
    version="4.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/search", response_model=SavedResult)
def search(q: str = Query(..., min_length=1, description="Search query")):
    """
    Scrape Reddit search results.
    
    URL: https://www.reddit.com/search.json?q=<query>
    
    Scrapes ALL posts and ALL comments.
    Saves to /data/reddit_<query>.json
    
    Just the query. Nothing else.
    """
    try:
        posts = scrape_search(q)
    except Exception as exc:
        logger.exception("Scraping failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))

    # Build output
    payload = {
        "query": q,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "count": len(posts),
        "posts": [p.model_dump() for p in posts],
    }

    # Save to file
    safe_q = re.sub(r"[^\w\-]", "_", q)[:60]
    filename = f"reddit_{safe_q}.json"
    out_path = OUTPUT_DIR / filename

    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not write file: {exc}")

    logger.info("✅ Saved %d posts → %s", len(posts), out_path)
    return SavedResult(query=q, count=len(posts), saved_to=str(out_path))
