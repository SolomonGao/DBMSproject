from pydantic import BaseModel, Field
from typing import Optional, Literal

class CalcInput(BaseModel):
    expression: str = Field(..., description="数学表达式")
    precision: int = Field(default=2, ge=0, le=10)

class SearchInput(BaseModel):
    query: str = Field(..., description="搜索关键词")