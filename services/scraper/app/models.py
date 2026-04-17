from pydantic import BaseModel
from typing import Optional, List


class Comment(BaseModel):
    """Represents a Reddit comment."""
    id: str
    author: str
    body: str
    score: int
    created_utc: float
    parent_id: Optional[str] = None
    is_submitter: bool = False  # True if comment author is the post author
    replies: List['Comment'] = []


class Post(BaseModel):
    id: str
    title: str
    url: str
    permalink: str
    score: int
    num_comments: int
    subreddit: str
    author: str
    created_utc: float
    selftext: str
    is_self: bool
    flair: Optional[str] = None
    comments: List[Comment] = []  # Top-level comments with nested replies


class SavedResult(BaseModel):
    query: str
    count: int
    saved_to: str         # absolute path inside the container  →  mounted to host


# Allow forward references for recursive model
Comment.model_rebuild()
