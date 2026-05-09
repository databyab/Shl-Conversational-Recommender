from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message content cannot be blank")
        return value


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)

    @field_validator("messages")
    @classmethod
    def must_include_user_message(cls, value: list[ChatMessage]) -> list[ChatMessage]:
        if not any(message.role == "user" for message in value):
            raise ValueError("at least one user message is required")
        return value

    def latest_user_message(self) -> ChatMessage:
        for message in reversed(self.messages):
            if message.role == "user":
                return message
        raise ValueError("at least one user message is required")
