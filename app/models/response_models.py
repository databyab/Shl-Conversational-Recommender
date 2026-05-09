from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Recommendation(BaseModel):
    name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    test_type: str = Field(min_length=1)

    @field_validator("url")
    @classmethod
    def url_must_be_catalog_url(cls, value: str) -> str:
        if not value.startswith("https://www.shl.com/products/product-catalog/view/"):
            raise ValueError("recommendation URL must come from the SHL product catalog")
        return value


class ChatResponse(BaseModel):
    reply: str = Field(min_length=1)
    recommendations: list[Recommendation] = Field(default_factory=list, max_length=10)
    end_of_conversation: bool = False
