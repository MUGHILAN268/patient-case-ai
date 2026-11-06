from typing import Optional

from pydantic import BaseModel, Field


class Patient(BaseModel):
    name: str
    abha_id: Optional[str] = ""
    age: Optional[int] = None
    gender: Optional[str] = ""
    complaint: str
    history: Optional[str] = ""
    symptoms: Optional[str] = ""
    medications: Optional[str] = ""
    allergies: Optional[str] = ""
    medical_history: Optional[str] = ""


class ChatRequest(BaseModel):
    patient_id: int
    message: str


class ChatReply(BaseModel):
    reply: str


class GeminiChatRequest(BaseModel):
    message: str
    conversation: list[dict[str, str]] = Field(default_factory=list)


class GeminiSummaryRequest(BaseModel):
    conversation: list[dict[str, str]] = Field(default_factory=list)
