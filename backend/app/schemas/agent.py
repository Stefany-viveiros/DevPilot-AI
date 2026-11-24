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
