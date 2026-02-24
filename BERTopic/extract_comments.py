"""
Extract Title and Comments from Reddit JSON
--------------------------------------------
Takes a Reddit scraper JSON file and extracts:
- Post title
- All comment bodies (flattened from nested structure)
- Comments sorted by score (upvotes) in descending order

Usage:
    python extract_comments.py <input_json> [output_json]

Example:
    python extract_comments.py reddit_google_perks_of_vyke_s_war_spear.json temp.json
    python extract_comments.py reddit_google_perks_of_vyke_s_war_spear.json  # outputs to temp.json by default
"""

import json
import sys
from pathlib import Path
from typing import List, Tuple


def extract_comments_recursive(comments: list) -> List[Tuple[str, int]]:
    """
    Recursively extract all comment bodies and scores from nested comment structure.
    
    Args:
        comments: List of comment objects, each may have 'replies' with more comments
    
    Returns:
        List of (body, score) tuples
    """
    results = []
    
    for comment in comments:
        # Get the body and score of this comment
        body = comment.get("body", "")
        score = comment.get("score", 0)
        
        if body and body not in ["[deleted]", "[removed]"]:
            results.append((body, score))
        
        # Recursively get replies
        replies = comment.get("replies", [])
        if replies:
            results.extend(extract_comments_recursive(replies))
    
    return results


def extract_from_reddit_json(input_path: str, output_path: str = "temp.json") -> dict:
    """
    Extract title and all comments from a Reddit scraper JSON file.
    Comments are sorted by score (upvotes) in descending order.
    
    Args:
        input_path: Path to the Reddit JSON file
        output_path: Path to save the extracted data
    
    Returns:
        Dictionary with 'title' and 'comments'
    """
    # Read input file
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Extract title from first post
    posts = data.get("posts", [])
    if not posts:
        print("[!] No posts found in the JSON file")
        return {"title": "", "comments": []}
    
    title = posts[0].get("title", "")
    print(f"Title: {title}")
    
    # Extract all comments recursively (with scores)
    all_comments_with_scores = []
    for post in posts:
        comments = post.get("comments", [])
        all_comments_with_scores.extend(extract_comments_recursive(comments))
    
    # Sort by score (descending order - highest first)
    all_comments_with_scores.sort(key=lambda x: x[1], reverse=True)
    
    # Extract just the bodies (now sorted by score)
    sorted_comments = [body for body, score in all_comments_with_scores]
    
    print(f"Found {len(sorted_comments)} comments")
    print(f"Top comment score: {all_comments_with_scores[0][1] if all_comments_with_scores else 0}")
    
    # Build output
    result = {
        "title": title,
        "comments": sorted_comments
    }
    
    # Save to output file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"Saved to: {output_path}")
    
    return result


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("[!] Error: No input file specified")
        print("\nUsage: python extract_comments.py <input_json> [output_json]")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "temp.json"
    
    if not Path(input_path).exists():
        print(f"[!] Error: File not found: {input_path}")
        sys.exit(1)
    
    extract_from_reddit_json(input_path, output_path)


if __name__ == "__main__":
    main()
