from typing import Optional
from pydantic import BaseModel

class ChatHistory(BaseModel):
    content: str
    role: str
    session_id: str
    sequence_number: int