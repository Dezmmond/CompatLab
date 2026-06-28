from typing import Literal

from pydantic import BaseModel, Field


Severity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]


class Problem(BaseModel):
    id: str
    severity: Severity
    title: str
    details: str
    artifact_path: str | None = None
    evidence: dict[str, str] = Field(default_factory=dict)
    suggestions: list[str] = Field(default_factory=list)
