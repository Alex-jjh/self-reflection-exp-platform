"""cells.jsonl: one request per line. The runtime validates shape only; it does
not interpret conditions.

    {"cell_id": str, "model": str, "system": str|null,
     "messages": [{"role": "user"|"assistant", "text": str}, ...],
     "inference": {"maxTokens": int, "temperature"?: num, "topP"?: num, "stopSequences"?: [str]},
     "additional": object|null,        # additionalModelRequestFields, passed through
     "meta": any}                      # optional, ignored, never sent or stored
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, Collection

from .util import ConfigError

ALLOWED_INFERENCE_KEYS = {"maxTokens", "temperature", "topP", "stopSequences"}
ALLOWED_CELL_KEYS = {"cell_id", "model", "system", "messages", "inference", "additional", "meta"}
REQUIRED_CELL_KEYS = {"cell_id", "model", "messages", "inference"}


@dataclasses.dataclass(frozen=True)
class Cell:
    cell_id: str
    model: str
    system: str | None
    messages: tuple[tuple[str, str], ...]
    inference: dict[str, Any]
    additional: dict[str, Any] | None


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_cell(obj: Any, allowed_models: Collection[str]) -> Cell:
    if not isinstance(obj, dict):
        raise ValueError("line is not a JSON object")
    missing = REQUIRED_CELL_KEYS - obj.keys()
    if missing:
        raise ValueError(f"missing field(s): {', '.join(sorted(missing))}")
    unknown = set(obj) - ALLOWED_CELL_KEYS
    if unknown:
        raise ValueError(f"unknown field(s): {', '.join(sorted(unknown))} (put free-form data under 'meta')")

    cell_id = obj["cell_id"]
    if not isinstance(cell_id, str) or not cell_id or len(cell_id) > 512 or any(c in cell_id for c in "\r\n\x00"):
        raise ValueError("cell_id must be a non-empty single-line string of at most 512 characters")

    model = obj["model"]
    if model not in allowed_models:
        raise ValueError(f"model {model!r} is not in the allowlist")

    system = obj.get("system")
    if system is not None and (not isinstance(system, str) or not system):
        raise ValueError("system must be null or a non-empty string")

    raw_messages = obj["messages"]
    if not isinstance(raw_messages, list) or not raw_messages:
        raise ValueError("messages must be a non-empty list")
    messages: list[tuple[str, str]] = []
    for index, message in enumerate(raw_messages):
        if not isinstance(message, dict) or set(message) != {"role", "text"}:
            raise ValueError(f"messages[{index}] must have exactly 'role' and 'text'")
        if message["role"] not in ("user", "assistant"):
            raise ValueError(f"messages[{index}].role must be 'user' or 'assistant'")
        if not isinstance(message["text"], str) or not message["text"]:
            raise ValueError(f"messages[{index}].text must be a non-empty string")
        messages.append((message["role"], message["text"]))
    if messages[0][0] != "user":
        raise ValueError("the first message must have role 'user'")

    inference = obj["inference"]
    if not isinstance(inference, dict):
        raise ValueError("inference must be an object")
    unknown_inference = set(inference) - ALLOWED_INFERENCE_KEYS
    if unknown_inference:
        raise ValueError(f"unsupported inference key(s): {', '.join(sorted(unknown_inference))}")
    max_tokens = inference.get("maxTokens")
    if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens < 1:
        raise ValueError("inference.maxTokens must be a positive integer")
    for key in ("temperature", "topP"):
        if key in inference and not _is_number(inference[key]):
            raise ValueError(f"inference.{key} must be a number")
    if "stopSequences" in inference and (
        not isinstance(inference["stopSequences"], list)
        or not all(isinstance(s, str) and s for s in inference["stopSequences"])
    ):
        raise ValueError("inference.stopSequences must be a list of non-empty strings")

    additional = obj.get("additional")
    if additional is not None and not isinstance(additional, dict):
        raise ValueError("additional must be null or an object")

    return Cell(
        cell_id=cell_id,
        model=model,
        system=system,
        messages=tuple(messages),
        inference=json.loads(json.dumps(inference)),
        additional=json.loads(json.dumps(additional)) if additional else None,
    )


def load_cells(path: Path, allowed_models: Collection[str]) -> list[Cell]:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"cells file not found: {path}")
    cells: list[Cell] = []
    errors: list[str] = []
    first_line: dict[str, int] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            text = line.strip()
            if not text:
                continue
            try:
                obj = json.loads(text)
            except json.JSONDecodeError as error:
                errors.append(f"line {line_no}: invalid JSON ({error.msg})")
                continue
            try:
                cell = parse_cell(obj, allowed_models)
            except ValueError as error:
                errors.append(f"line {line_no}: {error}")
                continue
            if cell.cell_id in first_line:
                errors.append(f"line {line_no}: duplicate cell_id (first seen on line {first_line[cell.cell_id]})")
                continue
            first_line[cell.cell_id] = line_no
            cells.append(cell)
    if errors:
        shown = "\n  ".join(errors[:25])
        more = f"\n  ... and {len(errors) - 25} more" if len(errors) > 25 else ""
        raise ConfigError(f"{len(errors)} invalid line(s) in {path}:\n  {shown}{more}")
    if not cells:
        raise ConfigError(f"no cells in {path}")
    return cells
