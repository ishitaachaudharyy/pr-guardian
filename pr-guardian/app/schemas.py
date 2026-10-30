from pydantic import BaseModel, Field
from typing import Literal

class Finding(BaseModel):
    title: str
    severity: Literal["critical", "high", "medium", "low", "info"] = "info"
    file: str | None = None
    line: int | None = None
    explanation: str
    recommendation: str
    confidence: float = Field(default=0.5, ge=0, le=1)
    source: str = "ai"

class AgentResult(BaseModel):
    agent: str
    findings: list[Finding] = []
    summary: str = ""
