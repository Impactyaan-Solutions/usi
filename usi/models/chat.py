from typing import Optional
from pydantic import BaseModel
from datetime import datetime
class ChatHistory(BaseModel):
    name: Optional[str] = None
    content: str
    role: str
    session_id: str
    sequence_number: int
    scheme: str | None = None

class ChatSession(BaseModel):
    name: str|None = None
    session_id: str | None = None
    scheme: str | None = None
    awaiting_clarification: str | None = None
    last_application_id: str | None = None
    last_classification_json: str | None = None
    status: str | None = None
    intent: str | None = None
    last_user_message_at: datetime | None = None