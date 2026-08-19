from pydantic import BaseModel, Field

class LanguageOption(BaseModel):
    code: str
    name: str

class JobCreatedResponse(BaseModel):
    job_id: str
    status: str

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    stage_message: str
    progress: int
    original_filename: str | None = None
    source_language: str | None = None
    target_language: str | None = None
    has_video: bool = False
    error: str | None = None
    artifacts: dict[str, str] = Field(default_factory=dict)
