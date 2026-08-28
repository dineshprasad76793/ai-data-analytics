from pydantic import BaseModel, Field
from typing import Any, Optional

class QueryRequest(BaseModel):
    dataset_id: str
    question: str = Field(min_length=1, max_length=1000)

class CleanRequest(BaseModel):
    dataset_id: str
    actions: list[dict[str, Any]] = []

class AnalysisRequest(BaseModel):
    dataset_id: str
    target_column: Optional[str] = None
    date_column: Optional[str] = None
    value_column: Optional[str] = None
