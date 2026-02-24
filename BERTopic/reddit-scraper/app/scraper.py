"""
Reddit Scraper - Simple & Complete
-----------------------------------
Just give it a search URL and it scrapes EVERYTHING.

URL: https://www.reddit.com/search.json?q=<your+query>

That's it. No parameters, no filters. Just raw results.
"""

import time
import logging
from typing import Optional, List

import httpx

from app.models import Post, Comment

logger = logging.getLogger(__name__)

REDDIT_BASE = "https://www.reddit.com"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}


def get_json(url: str) -> dict:
    """Get JSON from URL with retries and rate limit handling."""
    for attempt in range(10):  # 10 retries
        try:
            with httpx.Client(timeout=60, headers=_HEADERS, follow_redirects=True) as client:
                resp = client.get(url)

            # Rate limited - wait and retry
            if resp.status_code == 429:
                wait = float(resp.headers.get("Retry-After", 5 + attempt * 2))
                logger.warning("⚠️ Rate limited! Waiting %.0f seconds...", wait)
                time.sleep(wait)
                continue

            # Server error - wait and retry
            if resp.status_code >= 500:
                wait = 5 + attempt * 2
                logger.warning("⚠️ Server error %d. Waiting %d seconds...", resp.status_code, wait)
                time.sleep(wait)
                continue

            resp.raise_for_status()
            return resp.json()

        except httpx.TimeoutException:
            wait = 5 + attempt * 2
            logger.warning("⚠️ Timeout. Waiting %d seconds...", wait)
            time.sleep(wait)

    raise RuntimeError(f"Failed after 10 retries: {url}")


def parse_comment(data: dict, depth: int = 0) -> Optional[Comment]:
    """Parse a comment and all its replies."""
    if data.get("kind") != "t1":
        return None
    
    d = data.get("data", {})
    
    # Skip deleted
    if d.get("body") in ["[deleted]", "[removed]"]:
        return None
    
    comment = Comment(
        id=d.get("id", ""),
        author=d.get("author") or "[deleted]",
        body=d.get("body", ""),
        score=d.get("score", 0),
        created_utc=d.get("created_utc", 0.0),
        parent_id=d.get("parent_id"),
        is_submitter=d.get("is_submitter", False),
        replies=[],
    )
    
    # Parse replies (up to 20 levels deep)
    if depth < 20:
        replies_data = d.get("replies", {})
        if isinstance(replies_data, dict):
            for child in replies_data.get("data", {}).get("children", []):
                reply = parse_comment(child, depth + 1)
                if reply:
                    comment.replies.append(reply)
    
    return comment


def parse_post(data: dict) -> Post:
    """Parse a post."""
    d = data.get("data", {})
    permalink = d.get("permalink", "")
    return Post(
        id=d.get("id", ""),
        title=d.get("title", ""),
        url=d.get("url", ""),
        permalink=f"https://www.reddit.com{permalink}" if permalink else "",
        score=d.get("score", 0),
        num_comments=d.get("num_comments", 0),
        subreddit=d.get("subreddit", ""),
        author=d.get("author") or "[deleted]",
        created_utc=d.get("created_utc", 0.0),
        selftext=(d.get("selftext") or "").strip(),
        is_self=bool(d.get("is_self", False)),
        flair=d.get("link_flair_text"),
        comments=[],
    )


def get_comments(permalink: str) -> List[Comment]:
    """Get ALL comments for a post."""
    # Permalink might already be a full URL or just a path
    if permalink.startswith("https://www.reddit.com"):
        url = permalink.rstrip('/') + ".json?limit=500&depth=20"
    else:
        url = f"{REDDIT_BASE}{permalink.rstrip('/')}.json?limit=500&depth=20"
    
    try:
        data = get_json(url)
        
        if not isinstance(data, list) or len(data) < 2:
            return []
        
        comments = []
        for child in data[1].get("data", {}).get("children", []):
            comment = parse_comment(child)
            if comment:
                comments.append(comment)
        
        return comments
    except Exception as e:
        logger.error("Failed to get comments: %s", e)
        return []


def scrape_search(query: str) -> List[Post]:
    """
    Scrape ALL posts and comments from a Reddit search.
    
    Just the query - nothing else.
    URL: https://www.reddit.com/search.json?q=<query>
    """
    all_posts = []
    after = None
    page = 0
    
    # Build the URL - JUST the query
    search_url = f"{REDDIT_BASE}/search.json?q={query}"
    
    logger.info("=" * 70)
    logger.info("🔍 REDDIT SCRAPER")
    logger.info("=" * 70)
    logger.info("Query: %s", query)
    logger.info("URL: %s", search_url)
    logger.info("=" * 70)
    
    # Paginate through ALL results
    while True:
        page += 1
        
        # Build URL with pagination
        url = search_url
        if after:
            url = f"{search_url}&after={after}"
        
        logger.info("")
        logger.info("📄 Page %d | Total posts: %d", page, len(all_posts))
        
        data = get_json(url)
        listing = data.get("data", {})
        children = listing.get("children", [])
        
        if not children:
            logger.info("✅ No more results!")
            break
        
        # Parse posts
        for i, child in enumerate(children):
            if child.get("kind") != "t3":
                continue
            
            post = parse_post(child)
            
            # Get comments
            logger.info("  📝 [%d/%d] %s", i + 1, len(children), post.title[:60] + "..." if len(post.title) > 60 else post.title)
            post.comments = get_comments(post.permalink)
            logger.info("     💬 %d comments", len(post.comments))
            
            all_posts.append(post)
            
            # Small delay to avoid rate limiting
            time.sleep(0.1)
        
        # Get next page cursor
        after = listing.get("after")
        if not after:
            logger.info("✅ Reached the end!")
            break
        
        # Delay between pages
        time.sleep(0.3)
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("✅ SCRAPING COMPLETE!")
    logger.info("   Posts: %d", len(all_posts))
    logger.info("   Comments: %d", sum(len(p.comments) for p in all_posts))
    logger.info("=" * 70)
    
    return all_posts
