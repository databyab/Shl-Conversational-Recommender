from __future__ import annotations

import asyncio
import re
from pathlib import Path

from app.models.request_models import ChatMessage, ChatRequest
from app.orchestrator.controller import ChatController


USER_BLOCK_RE = re.compile(r"\*\*User\*\*\s*>\s*(.*?)(?=\n\n\*\*Agent\*\*|\n### Turn|\Z)", re.S)
TABLE_ROW_RE = re.compile(r"^\|\s*\d+\s*\|\s*([^|]+?)\s*\|", re.M)


def _clean_block(block: str) -> str:
    lines = []
    for line in block.splitlines():
        line = line.strip()
        if line.startswith(">"):
            line = line[1:].strip()
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def parse_conversation(path: Path) -> tuple[list[str], list[str]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    user_turns = [_clean_block(match.group(1)) for match in USER_BLOCK_RE.finditer(text)]
    expected_names = []
    for name in TABLE_ROW_RE.findall(text):
        name = re.sub(r"\s+", " ", name).strip("* _")
        if name and name not in expected_names:
            expected_names.append(name)
    return user_turns, expected_names


async def replay_file(path: Path, controller: ChatController | None = None) -> dict:
    controller = controller or ChatController()
    messages: list[ChatMessage] = []
    final_response = None
    user_turns, expected = parse_conversation(path)
    for turn in user_turns:
        messages.append(ChatMessage(role="user", content=turn))
        response = await controller.handle(ChatRequest(messages=messages))
        final_response = response
        messages.append(ChatMessage(role="assistant", content=response.reply))
    recommended = [rec.name for rec in final_response.recommendations] if final_response else []
    return {
        "file": str(path),
        "expected": expected,
        "recommended": recommended,
        "response": final_response.model_dump() if final_response else None,
    }


def replay_directory(directory: Path) -> list[dict]:
    controller = ChatController()

    async def _run() -> list[dict]:
        return [await replay_file(path, controller) for path in sorted(directory.glob("*.md"))]

    return asyncio.run(_run())
