from pydantic import BaseModel
from typing import List, Optional

class Citation(BaseModel):
    chunk_id: str
    document_id: str
    source_file: str
    page: Optional[int] = None
    char_start: int
    char_end: int

class QueryRequest(BaseModel):
    project_id: str
    question: str

class QueryResponse(BaseModel):
    answer: str
    citations: List[Citation]
