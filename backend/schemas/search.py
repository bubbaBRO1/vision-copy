from pydantic import BaseModel
from typing import Optional, Any
import uuid


class SearchResponse(BaseModel):
    search_id: str
    status: str
    filename: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}


class SearchResultResponse(BaseModel):
    search_id: str
    status: str
    results: Optional[dict] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: str
    completed_at: Optional[str] = None

    model_config = {"from_attributes": True}


class SearchHistoryItem(BaseModel):
    search_id: str
    filename: Optional[str]
    status: str
    created_at: str
    thumbnail: Optional[str] = None

    model_config = {"from_attributes": True}
