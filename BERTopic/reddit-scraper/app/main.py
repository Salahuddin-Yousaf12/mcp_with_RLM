"""
Reddit Scraper - Simple API
----------------------------
Two modes:
1. Direct Reddit search: GET /search?q=<query>
2. Google → Reddit: GET /google?q=<query> (finds first Reddit link via Google)

That's it. No parameters, no filters.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.scraper import scrape_search, scrape_via_google
from app.models import SavedResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("/data")

app = FastAPI(
    title="Reddit Scraper",
    description="Scrape Reddit posts. Use /search for Reddit search or /google for Google→Reddit.",
    version="5.0.0",
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
    Scrape Reddit search results directly.
    
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
        # Check if OUTPUT_DIR is a file (error condition) vs directory
        if OUTPUT_DIR.exists() and OUTPUT_DIR.is_file():
            # Remove the file so we can create the directory
            OUTPUT_DIR.unlink()
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not write file: {exc}")

    logger.info("✅ Saved %d posts → %s", len(posts), out_path)
    return SavedResult(query=q, count=len(posts), saved_to=str(out_path))


@app.get("/google", response_model=SavedResult)
def google_search(q: str = Query(..., min_length=1, description="Search query")):
    """
    Search Google, find the first Reddit link, and scrape it.
    
    1. Searches Google for: <query> site:reddit.com
    2. Finds the first Reddit URL in results
    3. Scrapes that Reddit post + all comments
    4. Saves to /data/reddit_google_<query>.json
    
    Great for finding the most relevant Reddit discussion about a topic.
    """
    try:
        posts = scrape_via_google(q)
    except Exception as exc:
        logger.exception("Google search scraping failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))

    if not posts:
        raise HTTPException(status_code=404, detail="No Reddit results found via Google search")

    # Build output
    payload = {
        "query": q,
        "source": "google",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "count": len(posts),
        "posts": [p.model_dump() for p in posts],
    }

    # Save to file
    safe_q = re.sub(r"[^\w\-]", "_", q)[:60]
    filename = f"reddit_google_{safe_q}.json"
    out_path = OUTPUT_DIR / filename

    try:
        # Check if OUTPUT_DIR is a file (error condition) vs directory
        if OUTPUT_DIR.exists() and OUTPUT_DIR.is_file():
            OUTPUT_DIR.unlink()
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not write file: {exc}")

    logger.info("✅ Saved %d posts → %s", len(posts), out_path)
    return SavedResult(query=q, count=len(posts), saved_to=str(out_path))
