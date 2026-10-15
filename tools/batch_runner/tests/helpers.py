"""Test helpers: a fake bedrock-runtime client and small cell files."""

from __future__ import annotations

import dataclasses
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from botocore.exceptions import ClientError  # noqa: E402

from bedrock_access import BedrockConverseBackend  # noqa: E402
from experiment_runtime.engine import RunConfig  # noqa: E402

MODEL_A = "us.anthropic.claude-sonnet-5"
MODEL_B = "us.openai.gpt-5.6-luna"


@dataclasses.dataclass
class FakeCall:
    cell_id: str
    model: str
    n: int  # 1-based call number for this cell
    request: dict[str, Any]


def cell_id_of(request: dict[str, Any]) -> str:
    text = request["messages"][0]["content"][0]["text"]
    return text.split("cell:", 1)[1].split()[0]


def ok_response(text: str = "ok", out_tokens: int = 5, reasoning: str | None = None) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    if reasoning is not None:
        content.append({"reasoningContent": {"reasoningText": {"text": reasoning, "signature": "sig"}}})
    content.append({"text": text})
    return {
        "output": {"message": {"role": "assistant", "content": content}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 3, "outputTokens": out_tokens, "totalTokens": 3 + out_tokens},
        "metrics": {"latencyMs": 1},
    }


def client_error(code: str, status: int, message: str = "fake error") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": message},
                        "ResponseMetadata": {"HTTPStatusCode": status}}, "Converse")


class FakeBedrockClient:
    """Stands in for boto3's bedrock-runtime client; ``behaviour(call)`` returns or raises."""

    def __init__(self, behaviour: Callable[[FakeCall], Any] | None = None):
        self.behaviour = behaviour or (lambda call: ok_response(f"reply for {call.cell_id}"))
        self.calls: list[FakeCall] = []
        self.lock = threading.Lock()
        self.in_flight = 0
        self.max_in_flight = 0

    def converse(self, **request: Any) -> dict[str, Any]:
        cell_id = cell_id_of(request)
        with self.lock:
            n = sum(1 for call in self.calls if call.cell_id == cell_id) + 1
            call = FakeCall(cell_id, request["modelId"], n, request)
            self.calls.append(call)
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            return self.behaviour(call)
        finally:
            with self.lock:
                self.in_flight -= 1

    def called_ids(self) -> list[str]:
        with self.lock:
            return [call.cell_id for call in self.calls]


class CountingFactory:
    def __init__(self, client: FakeBedrockClient):
        self.client = client
        self.created = 0

    def __call__(self, region: str) -> FakeBedrockClient:
        self.created += 1
        return self.client


def fake_backend(client: FakeBedrockClient) -> tuple[BedrockConverseBackend, CountingFactory]:
    factory = CountingFactory(client)
    return BedrockConverseBackend(client_factory=factory), factory


def write_cells(path: Path, per_model: int = 5, models: tuple[str, ...] = (MODEL_A, MODEL_B),
                conditions: tuple[str, ...] = ("A", "B", "C")) -> list[str]:
    """Cell ids encode a condition (as real ones do) so blinding can be checked."""
    ids = []
    with path.open("w", encoding="utf-8") as handle:
        for model in models:
            for index in range(per_model):
                condition = conditions[index % len(conditions)]
                cell_id = f"cond={condition}|item={index}|model={model}"
                ids.append(cell_id)
                handle.write(json.dumps({
                    "cell_id": cell_id,
                    "model": model,
                    "system": f"system prompt for condition {condition}",
                    "messages": [
                        {"role": "user", "text": f"cell:{cell_id} first question"},
                        {"role": "assistant", "text": "an earlier answer"},
                        {"role": "user", "text": "follow-up question"},
                    ],
                    "inference": {"maxTokens": 50},
                    "additional": {"reasoning_effort": "low"} if condition == "B" else None,
                }) + "\n")
    return ids


def fast_config(cells: Path, out: Path, **overrides: Any) -> RunConfig:
    values: dict[str, Any] = dict(
        cells_path=cells,
        out_dir=out,
        max_concurrency=4,
        initial_concurrency=4,
        increase_after=3,
        backoff_base=0.002,
        backoff_cap=0.01,
        credential_retry_interval=0.1,
        credential_max_wait=30.0,
        shutdown_timeout=5.0,
        progress_interval=0.2,
        code_sha256="test-sha",
    )
    values.update(overrides)
    return RunConfig(**values)


def wait_until(predicate: Callable[[], bool], timeout: float = 10.0, interval: float = 0.01) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False
