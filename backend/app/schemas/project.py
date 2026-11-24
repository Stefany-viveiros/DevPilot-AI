from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    root_path: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("O nome do projeto não pode ficar vazio.")
        return value

class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    root_path: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("O nome do projeto não pode ficar vazio.")
        return value

class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    root_path: str | None
    status: str
    last_analyzed_at: datetime | None
    created_at: datetime
    updated_at: datetime

class ProjectAnalysisRead(BaseModel):
    project_id: int
    project_name: str
    analyzed_at: datetime
    detected_technologies: list[str]
    language_file_counts: dict[str, int]
    manifest_hints: list[str]
    entrypoints: list[str]
    files: list[str]
    total_files: int
    files_listed: int
    files_omitted_from_list: int

class ProjectEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    event_type: str
    summary: str
    details_json: str | None
    created_at: datetime
