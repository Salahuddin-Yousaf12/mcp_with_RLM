"""
Reddit Scraper - Google Search + Reddit Scraping
-------------------------------------------------
1. Search Google for the query
2. Find the first reddit.com link
3. Scrape that Reddit page (post + comments)

Alternative: Use Reddit's JSON API directly for search.
"""

import time
import logging
import re
import urllib.parse
from typing import Optional, List

import httpx

from app.models import Post, Comment

logger = logging.getLogger(__name__)

REDDIT_BASE = "https://www.reddit.com"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

_GOOGLE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
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


def get_html(url: str) -> str:
    """Get HTML from URL with retries."""
    for attempt in range(5):
        try:
            with httpx.Client(timeout=30, headers=_GOOGLE_HEADERS, follow_redirects=True) as client:
                resp = client.get(url)

            if resp.status_code == 429:
                wait = 5 + attempt * 2
                logger.warning("⚠️ Rate limited! Waiting %d seconds...", wait)
                time.sleep(wait)
                continue

            if resp.status_code >= 500:
                wait = 3 + attempt * 2
                logger.warning("⚠️ Server error %d. Waiting %d seconds...", resp.status_code, wait)
                time.sleep(wait)
                continue

            resp.raise_for_status()
            return resp.text

        except httpx.TimeoutException:
            wait = 3 + attempt * 2
            logger.warning("⚠️ Timeout. Waiting %d seconds...", wait)
            time.sleep(wait)

    raise RuntimeError(f"Failed to fetch HTML: {url}")


def search_google_for_reddit(query: str) -> Optional[str]:
    """
    Search Google for the query and return the first reddit.com link found.
    
    Returns the Reddit URL or None if no Reddit link is found.
    """
    # Add "site:reddit.com" to the query to prioritize Reddit results
    search_query = f"{query} site:reddit.com"
    encoded_query = urllib.parse.quote(search_query)
    google_url = f"https://www.google.com/search?q={encoded_query}&num=20"
    
    logger.info("🔍 Searching Google: %s", google_url)
    
    html = get_html(google_url)
    
    # Log a snippet for debugging
    logger.debug("HTML snippet: %s", html[:2000])
    
    # Multiple patterns to find Reddit URLs in Google search results
    found_reddit_urls = []
    
    # Pattern 1: /url?q=... format (most common)
    url_pattern = r'/url\?q=([^&"\s]+)'
    for match in re.finditer(url_pattern, html):
        url = urllib.parse.unquote(match.group(1))
        if 'reddit.com' in url:
            # Clean up the URL
            clean_url = url.split('&')[0]
            if clean_url not in found_reddit_urls:
                found_reddit_urls.append(clean_url)
                logger.info("  Found via /url?q=: %s", clean_url)
    
    # Pattern 2: Direct href="https://www.reddit.com/..." links
    href_pattern = r'href=["\']?(https?://(?:www\.)?reddit\.com/[^"\'\s>]+)["\']?'
    for match in re.finditer(href_pattern, html):
        url = match.group(1)
        if url not in found_reddit_urls:
            found_reddit_urls.append(url)
            logger.info("  Found via href: %s", url)
    
    # Pattern 3: Any reddit.com URL anywhere in the HTML
    general_pattern = r'https?://(?:www\.)?reddit\.com/[^\s"\'<>]+'
    for match in re.finditer(general_pattern, html):
        url = match.group(0)
        # Clean trailing punctuation
        url = url.rstrip('.,;:!?)')
        if url not in found_reddit_urls:
            found_reddit_urls.append(url)
            logger.info("  Found via general pattern: %s", url)
    
    # Pattern 4: Look in data-href or other attributes
    data_href_pattern = r'data-href=["\']?(https?://(?:www\.)?reddit\.com/[^"\'\s>]+)["\']?'
    for match in re.finditer(data_href_pattern, html):
        url = match.group(1)
        if url not in found_reddit_urls:
            found_reddit_urls.append(url)
            logger.info("  Found via data-href: %s", url)
    
    # Return the first valid Reddit URL (skip Reddit homepage or generic links)
    for url in found_reddit_urls:
        # Skip if it's just the homepage or very short
        if len(url) < 30:
            continue
        # Skip if it's just reddit.com or reddit.com/r/
        if url in ['https://www.reddit.com', 'https://reddit.com', 
                   'https://www.reddit.com/', 'https://reddit.com/']:
            continue
        # We want actual post/comment links
        logger.info("✅ Selected Reddit URL: %s", url)
        return url
    
    # If we found any Reddit URLs at all, return the first one
    if found_reddit_urls:
        logger.info("✅ Using first found Reddit URL: %s", found_reddit_urls[0])
        return found_reddit_urls[0]
    
    logger.warning("❌ No Reddit URL found in Google search results")
    return None


def search_duckduckgo_for_reddit(query: str) -> Optional[str]:
    """
    Fallback: Search DuckDuckGo for Reddit links.
    DuckDuckGo is often more scraper-friendly than Google.
    """
    search_query = f"{query} site:reddit.com"
    encoded_query = urllib.parse.quote(search_query)
    ddg_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    
    logger.info("🔍 Searching DuckDuckGo: %s", ddg_url)
    
    try:
        html = get_html(ddg_url)
        
        # DuckDuckGo HTML results have links in <a class="result__a" href="...">
        # The actual URL is usually after u= in the href
        patterns = [
            r'uddg=([^&"\s]+)',  # DuckDuckGo redirect URL
            r'href=["\']?(https?://(?:www\.)?reddit\.com/[^"\'\s>]+)["\']?',
            r'https?://(?:www\.)?reddit\.com/[^\s"\'<>]+',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, html):
                url = urllib.parse.unquote(match.group(1) if match.lastindex else match.group(0))
                if 'reddit.com' in url and len(url) > 30:
                    # Clean up
                    url = url.split('&')[0].rstrip('.,;:!?)')
                    logger.info("✅ Found Reddit URL via DuckDuckGo: %s", url)
                    return url
    except Exception as e:
        logger.warning("DuckDuckGo search failed: %s", e)
    
    return None


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


def scrape_single_post(reddit_url: str) -> Optional[Post]:
    """
    Scrape a single Reddit post from its URL.
    
    Args:
        reddit_url: Full Reddit URL (e.g., https://www.reddit.com/r/.../comments/.../...)
    
    Returns:
        Post object with comments, or None if failed.
    """
    logger.info("=" * 70)
    logger.info("🔍 SCRAPING SINGLE REDDIT POST")
    logger.info("=" * 70)
    logger.info("URL: %s", reddit_url)
    
    # Ensure we have the .json endpoint
    json_url = reddit_url.rstrip('/')
    if not json_url.endswith('.json'):
        json_url = f"{json_url}.json"
    
    # Add parameters for more comments
    if '?' in json_url:
        json_url = f"{json_url}&limit=500&depth=20"
    else:
        json_url = f"{json_url}?limit=500&depth=20"
    
    try:
        data = get_json(json_url)
        
        # Reddit post data comes as a list: [post_data, comments_data]
        if not isinstance(data, list) or len(data) < 1:
            logger.error("❌ Unexpected response format")
            return None
        
        # Extract post data
        post_listing = data[0].get("data", {})
        post_children = post_listing.get("children", [])
        
        if not post_children:
            logger.error("❌ No post found")
            return None
        
        post = parse_post(post_children[0])
        
        # Get comments
        logger.info("📝 Post: %s", post.title[:60] + "..." if len(post.title) > 60 else post.title)
        post.comments = get_comments(reddit_url)
        logger.info("💬 %d comments", len(post.comments))
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ SCRAPING COMPLETE!")
        logger.info("   Comments: %d", len(post.comments))
        logger.info("=" * 70)
        
        return post
        
    except Exception as e:
        logger.error("❌ Failed to scrape post: %s", e)
        return None


def scrape_via_google(query: str) -> List[Post]:
    """
    Search Google for the query, find the first Reddit link, and scrape it.
    
    Falls back to DuckDuckGo if Google doesn't find anything.
    
    Args:
        query: Search query (e.g., "best python tutorials")
    
    Returns:
        List containing the scraped post (or empty list if failed).
    """
    logger.info("=" * 70)
    logger.info("🔍 SEARCH ENGINE → REDDIT SCRAPER")
    logger.info("=" * 70)
    logger.info("Query: %s", query)
    
    # Step 1: Try Google first
    reddit_url = search_google_for_reddit(query)
    
    # Step 2: If Google fails, try DuckDuckGo
    if not reddit_url:
        logger.info("⚠️ Google didn't find Reddit URL, trying DuckDuckGo...")
        reddit_url = search_duckduckgo_for_reddit(query)
    
    if not reddit_url:
        logger.warning("❌ No Reddit URL found for query: %s", query)
        return []
    
    # Step 3: Scrape the Reddit post
    post = scrape_single_post(reddit_url)
    
    if post:
        return [post]
    
    return []
