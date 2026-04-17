"""
Reddit functions — search and scrape Reddit discussions.

These functions are registered automatically on import and become
available to the LLM in the REPL namespace.
"""

import re
import time
import logging
import urllib.parse
from typing import Optional, List, Tuple

import httpx

from .registry import registry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

_SEARCH_HEADERS = {
    **_HEADERS,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

REDDIT_BASE = "https://www.reddit.com"


def _get_json(url: str, retries: int = 5) -> dict:
    for attempt in range(retries):
        try:
            with httpx.Client(timeout=60, headers=_HEADERS, follow_redirects=True) as c:
                r = c.get(url)
            if r.status_code == 429:
                time.sleep(float(r.headers.get("Retry-After", 3 + attempt * 2)))
                continue
            if r.status_code >= 500:
                time.sleep(3 + attempt * 2)
                continue
            r.raise_for_status()
            return r.json()
        except httpx.TimeoutException:
            time.sleep(3 + attempt * 2)
    raise RuntimeError(f"Failed after {retries} retries: {url}")


def _get_html(url: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            with httpx.Client(timeout=30, headers=_SEARCH_HEADERS, follow_redirects=True) as c:
                r = c.get(url)
            if r.status_code in (429, 500, 502, 503):
                time.sleep(3 + attempt * 2)
                continue
            r.raise_for_status()
            return r.text
        except httpx.TimeoutException:
            time.sleep(3 + attempt * 2)
    raise RuntimeError(f"Failed to fetch HTML: {url}")


# ---------------------------------------------------------------------------
# Search engine chain: Google -> DuckDuckGo -> Bing -> Reddit API
# ---------------------------------------------------------------------------

def _search_google(query: str) -> Optional[str]:
    encoded = urllib.parse.quote(f"{query} site:reddit.com")
    try:
        html = _get_html(f"https://www.google.com/search?q={encoded}&num=20")
    except Exception:
        return None
    for pattern in [
        r'/url\?q=([^&"\s]+)',
        r'href=["\']?(https?://(?:www\.)?reddit\.com/[^"\'\s>]+)',
        r'https?://(?:www\.)?reddit\.com/[^\s"\'<>]+',
    ]:
        for m in re.finditer(pattern, html):
            url = urllib.parse.unquote(m.group(1) if m.lastindex else m.group(0))
            url = url.split("&")[0].rstrip(".,;:!?)")
            if "reddit.com" in url and len(url) > 30:
                return url
    return None


def _search_duckduckgo(query: str) -> Optional[str]:
    encoded = urllib.parse.quote(f"{query} site:reddit.com")
    try:
        html = _get_html(f"https://html.duckduckgo.com/html/?q={encoded}")
    except Exception:
        return None
    for pattern in [
        r'uddg=([^&"\s]+)',
        r'href=["\']?(https?://(?:www\.)?reddit\.com/[^"\'\s>]+)',
    ]:
        for m in re.finditer(pattern, html):
            url = urllib.parse.unquote(m.group(1) if m.lastindex else m.group(0))
            url = url.split("&")[0].rstrip(".,;:!?)")
            if "reddit.com" in url and len(url) > 30:
                return url
    return None


def _search_bing(query: str) -> Optional[str]:
    encoded = urllib.parse.quote(f"{query} site:reddit.com")
    try:
        html = _get_html(f"https://www.bing.com/search?q={encoded}&count=20")
    except Exception:
        return None
    for pattern in [
        r'href=["\']?(https?://(?:www\.)?reddit\.com/[^"\'\s>]+)',
        r'https?://(?:www\.)?reddit\.com/[^\s"\'<>]+',
    ]:
        for m in re.finditer(pattern, html):
            url = urllib.parse.unquote(m.group(1) if m.lastindex else m.group(0))
            url = url.split("&")[0].rstrip(".,;:!?)")
            if "reddit.com" in url and len(url) > 30:
                return url
    return None


def _search_reddit_api(query: str) -> Optional[str]:
    url = f"{REDDIT_BASE}/search.json?q={urllib.parse.quote(query)}&sort=relevance&limit=5&type=link"
    try:
        data = _get_json(url)
        for child in data.get("data", {}).get("children", []):
            permalink = child.get("data", {}).get("permalink", "")
            if permalink:
                return f"{REDDIT_BASE}{permalink}"
    except Exception:
        pass
    return None


def _find_reddit_url(query: str) -> Optional[str]:
    """Try all search engines in order, return the first Reddit URL found."""
    for search_fn in [_search_google, _search_duckduckgo, _search_bing, _search_reddit_api]:
        url = search_fn(query)
        if url:
            return url
    return None


# ---------------------------------------------------------------------------
# Post + comment parsing
# ---------------------------------------------------------------------------

def _parse_comment(data: dict, depth: int = 0) -> Optional[dict]:
    if data.get("kind") != "t1":
        return None
    d = data.get("data", {})
    body = d.get("body", "")
    if body in ("[deleted]", "[removed]", ""):
        return None
    comment = {
        "body": body,
        "score": d.get("score", 0),
        "author": d.get("author", "[deleted]"),
        "replies": [],
    }
    if depth < 20:
        replies_data = d.get("replies", {})
        if isinstance(replies_data, dict):
            for child in replies_data.get("data", {}).get("children", []):
                reply = _parse_comment(child, depth + 1)
                if reply:
                    comment["replies"].append(reply)
    return comment


def _scrape_post(reddit_url: str) -> Optional[dict]:
    """Scrape a single Reddit post and its comments."""
    json_url = reddit_url.rstrip("/")
    if not json_url.endswith(".json"):
        json_url += ".json"
    json_url += ("&" if "?" in json_url else "?") + "limit=500&depth=20"

    data = _get_json(json_url)
    if not isinstance(data, list) or len(data) < 1:
        return None

    post_children = data[0].get("data", {}).get("children", [])
    if not post_children:
        return None

    pd = post_children[0].get("data", {})
    post = {
        "title": pd.get("title", ""),
        "selftext": (pd.get("selftext") or "").strip(),
        "score": pd.get("score", 0),
        "subreddit": pd.get("subreddit", ""),
        "author": pd.get("author", "[deleted]"),
        "comments": [],
    }

    if len(data) >= 2:
        for child in data[1].get("data", {}).get("children", []):
            comment = _parse_comment(child)
            if comment:
                post["comments"].append(comment)

    return post


def _extract_comments_flat(comments: list) -> List[Tuple[str, int, str]]:
    """Recursively flatten comments into (body, score, author) tuples."""
    results = []
    for c in comments:
        results.append((c["body"], c["score"], c["author"]))
        results.extend(_extract_comments_flat(c.get("replies", [])))
    return results


def _format_post(post: dict) -> str:
    """Format a post + comments into a readable text string."""
    flat = _extract_comments_flat(post["comments"])
    flat.sort(key=lambda x: x[1], reverse=True)

    parts = [f"POST TITLE: {post['title']}"]
    if post["selftext"]:
        parts.append(f"POST BODY:\n{post['selftext']}")
    parts.append(f"SUBREDDIT: r/{post['subreddit']}  |  POST SCORE: {post['score']}")
    parts.append(f"TOTAL COMMENTS: {len(flat)}")
    parts.append("")

    for i, (body, score, author) in enumerate(flat, 1):
        parts.append(f"COMMENT {i} (score: {score}, by u/{author}):\n{body}")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Registered functions (available to the LLM in the REPL)
# ---------------------------------------------------------------------------

@registry.register(
    description="Search Reddit for a topic, scrape the top post and all comments, "
                "return the full discussion as text (sorted by score)"
)
def search_reddit(query: str) -> str:
    """Search Reddit for a topic and return the full discussion."""
    url = _find_reddit_url(query)
    if not url:
        return f"[No Reddit results found for: {query}]"

    post = _scrape_post(url)
    if not post:
        return f"[Failed to scrape Reddit post at: {url}]"

    return _format_post(post)


@registry.register(
    description="Scrape a specific Reddit post URL and return its comments as text"
)
def scrape_reddit_url(url: str) -> str:
    """Scrape a specific Reddit post by URL."""
    post = _scrape_post(url)
    if not post:
        return f"[Failed to scrape: {url}]"
    return _format_post(post)


@registry.register(
    description="Quick search Reddit and return just the top post titles with scores (no comments)"
)
def list_reddit_posts(query: str) -> str:
    """Search Reddit and list matching post titles."""
    api_url = (
        f"{REDDIT_BASE}/search.json"
        f"?q={urllib.parse.quote(query)}&sort=relevance&limit=10&type=link"
    )
    try:
        data = _get_json(api_url)
    except Exception as e:
        return f"[Reddit search failed: {e}]"

    children = data.get("data", {}).get("children", [])
    if not children:
        return f"[No posts found for: {query}]"

    lines = [f"Found {len(children)} posts for '{query}':\n"]
    for i, child in enumerate(children, 1):
        d = child.get("data", {})
        title = d.get("title", "")
        score = d.get("score", 0)
        num_comments = d.get("num_comments", 0)
        subreddit = d.get("subreddit", "")
        permalink = d.get("permalink", "")
        lines.append(
            f"  {i}. [{score} pts, {num_comments} comments] r/{subreddit}: {title}"
            f"\n     https://www.reddit.com{permalink}"
        )

    return "\n".join(lines)
