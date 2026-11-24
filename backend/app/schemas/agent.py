from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class TaskCreate(BaseModel):
    instruction: str = Field(min_length=8, max_length=4000)

class AgentPlan(BaseModel):
    summary: str
    steps: list[dict[str, str]]
    proposed_changes: list[dict[str, str]] = []
    risks: list[str] = []

class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    instruction: str
    status: str
    plan_json: str
    result_json: str | None
    created_at: datetime
    updated_at: datetime


class MemoryWrite(BaseModel):
    memory_key: str = Field(min_length=2, max_length=120, pattern=r"^[a-zA-Z0-9_.-]+$")
    content: str = Field(min_length=1, max_length=8000)

class MemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    memory_key: str
    content: str
    source: str
    updated_at: datetime
