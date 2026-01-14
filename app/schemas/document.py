from pydantic import BaseModel
from datetime import datetime

class DocumentBase(BaseModel):
    filename: str

class DocumentCreate(DocumentBase):
    project_id: str
    file_path: str

class Document(DocumentBase):
    id: str
    project_id: str
    created_at: datetime

    class Config:
        from_attributes = True
