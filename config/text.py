from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List


@dataclass
class TextReplacement:
    """A literal text replacement to apply before speech synthesis."""

    from_text: str
    to_text: str


@dataclass
class TextConfig:
    """Configuration for text processing and sanitization."""

    ignore_chars: List[str] = field(default_factory=list)
    ignore_newline: bool = False
    replacements: List[TextReplacement] = field(default_factory=list)


def load_text_config(path: str) -> TextConfig:
    """Load text configuration from a JSON file.

    Expected shape:
    {
      "text": {
        "ignore_chars": ["*", "\n"],
        "replacements": [
          {"from": "asyncio", "to": "Async IO"}
        ]
      }
    }
    """

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Config file must contain a JSON object")

    text_data = data.get("text", {})
    if not isinstance(text_data, dict):
        raise ValueError("Config field 'text' must be an object")

    ignore_chars = text_data.get("ignore_chars", [])
    if not isinstance(ignore_chars, list) or not all(
        isinstance(item, str) for item in ignore_chars
    ):
        raise ValueError("Config field 'text.ignore_chars' must be a list of strings")

    replacements_data = text_data.get("replacements", [])
    if not isinstance(replacements_data, list):
        raise ValueError("Config field 'text.replacements' must be a list")

    replacements: List[TextReplacement] = []
    for index, item in enumerate(replacements_data):
        replacements.append(_parse_replacement(index, item))

    return TextConfig(ignore_chars=ignore_chars, replacements=replacements)


def _parse_replacement(index: int, item: Any) -> TextReplacement:
    if not isinstance(item, dict):
        raise ValueError(f"Replacement at index {index} must be an object")

    from_text = item.get("from")
    to_text = item.get("to")
    if not isinstance(from_text, str) or not from_text:
        raise ValueError(f"Replacement at index {index} must have a non-empty 'from'")
    if not isinstance(to_text, str):
        raise ValueError(f"Replacement at index {index} must have a string 'to'")

    return TextReplacement(from_text=from_text, to_text=to_text)
