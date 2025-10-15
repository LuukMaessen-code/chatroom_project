from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Server(BaseModel):
    id: int
    name: str


class ChatMessage(BaseModel):
    type: Literal["message", "system"]
    serverId: int = Field(alias="server_id")
    username: Optional[str] = None
    text: Optional[str] = None
    event: Optional[Literal["join", "leave"]] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("text")
    @classmethod
    def _trim_text(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        t = v.strip()
        return t if t else None

    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda dt: dt.astimezone(timezone.utc).isoformat()}
