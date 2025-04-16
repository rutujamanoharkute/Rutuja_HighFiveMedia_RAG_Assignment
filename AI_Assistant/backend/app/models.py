from pydantic import BaseModel
from typing import List, Optional


class AuditLog(BaseModel):
    is_flagged: bool
    flagged_categories: List[str] = []
    sanitized_text: Optional[str] = None
    timestamp: Optional[str] = None
    
class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    audit_log: Optional[AuditLog] = None 

class UploadResponse(BaseModel):
    message: str
    file_ids: List[str]

class AnalysisReport(BaseModel):
    message: str
    report_path: str