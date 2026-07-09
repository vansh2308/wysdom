from pydantic import BaseModel, Field


class CodeChunk(BaseModel):
    id: str
    type: str
    name: str
    language: str
    path: str
    start_line: int
    end_line: int
    content: str
    parent_name: str | None = None
    parent_type: str | None = None
    superclasses: list[str] = Field(default_factory=list)
    related_comments: list[str] = Field(default_factory=list)
    where_used: list[str] = Field(default_factory=list)
