"""
Extract Title and Comments from Reddit JSON
--------------------------------------------
Takes a Reddit scraper JSON file and extracts:
- Post title
- All comment bodies (flattened from nested structure)

Usage:
    python extract_comments.py <input_json> [output_json]

Example:
    python extract_comments.py reddit_google_perks_of_vyke_s_war_spear.json temp.json
    python extract_comments.py reddit_google_perks_of_vyke_s_war_spear.json  # outputs to temp.json by default
"""

import json
import sys
from pathlib import Path
from typing import List


def extract_comments_recursive(comments: list) -> List[str]:
    """
    Recursively extract all comment bodies from nested comment structure.
    
    Args:
        comments: List of comment objects, each may have 'replies' with more comments
    
    Returns:
        Flat list of all comment bodies
    """
    bodies = []
    
    for comment in comments:
        # Get the body of this comment
        body = comment.get("body", "")
        if body and body not in ["[deleted]", "[removed]"]:
            bodies.append(body)
        
        # Recursively get replies
        replies = comment.get("replies", [])
        if replies:
            bodies.extend(extract_comments_recursive(replies))
    
    return bodies


def extract_from_reddit_json(input_path: str, output_path: str = "temp.json") -> dict:
    """
    Extract title and all comments from a Reddit scraper JSON file.
    
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
    
    # Extract all comments recursively
    all_comments = []
    for post in posts:
        comments = post.get("comments", [])
        all_comments.extend(extract_comments_recursive(comments))
    
    print(f"Found {len(all_comments)} comments")
    
    # Build output
    result = {
        "title": title,
        "comments": all_comments
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
