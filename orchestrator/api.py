"""
MCP Service — FastAPI orchestrator

POST /ask  { "q": "..." }  →  { "answer": "..." }

Flow:
  1. GET reddit-scraper /google?q=...   → saved_to path
  2. Read scraped JSON from shared volume → extract title + comments
  3. POST rlm-service /query            → final answer
"""

import json
import os
from pathlib import Path
from typing import List, Tuple

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

REDDIT_SCRAPER_URL = os.getenv("REDDIT_SCRAPER_URL", "http://reddit-scraper:8000")
RLM_SERVICE_URL = os.getenv("RLM_SERVICE_URL", "http://rlm-service:8002")
SCRAPE_TIMEOUT = 120.0
RLM_TIMEOUT = 300.0

app = FastAPI(title="MCP Service", version="1.0.0")


class AskRequest(BaseModel):
    q: str


class AskResponse(BaseModel):
    answer: str


# ---------------------------------------------------------------------------
# Comment extraction (inlined from extract_comments.py — no subprocess needed)
# ---------------------------------------------------------------------------

def _extract_recursive(comments: list) -> List[Tuple[str, int]]:
    results = []
    for comment in comments:
        body = comment.get("body", "")
        score = comment.get("score", 0)
        if body and body not in ["[deleted]", "[removed]"]:
            results.append((body, score))
        replies = comment.get("replies", [])
        if replies:
            results.extend(_extract_recursive(replies))
    return results


def _build_context(saved_to: str) -> str:
    data = json.loads(Path(saved_to).read_text(encoding="utf-8"))
    posts = data.get("posts", [])
    if not posts:
        raise ValueError("No posts found in scraped file")

    title = posts[0].get("title", "")
    all_comments: List[Tuple[str, int]] = []
    for post in posts:
        all_comments.extend(_extract_recursive(post.get("comments", [])))

    all_comments.sort(key=lambda x: x[1], reverse=True)

    parts = [f"POST TITLE: {title}"]
    for i, (body, _) in enumerate(all_comments, 1):
        parts.append(f"COMMENT {i}:\n{body}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    # Step 1 — scrape Reddit via Google
    with httpx.Client(timeout=SCRAPE_TIMEOUT) as client:
        r = client.get(f"{REDDIT_SCRAPER_URL}/google", params={"q": req.q})

    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    saved_to = r.json().get("saved_to", "")
    if not saved_to:
        raise HTTPException(status_code=500, detail="Scraper returned no file path")

    # Step 2 — extract comments from the scraped file
    try:
        context = _build_context(saved_to)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comment extraction failed: {e}")

    # Step 3 — ask RLM for a final answer
    with httpx.Client(timeout=RLM_TIMEOUT) as client:
        r = client.post(
            f"{RLM_SERVICE_URL}/query",
            json={"query": req.q, "context": context},
        )

    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    return AskResponse(answer=r.json()["answer"])
