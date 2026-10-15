"""Bedrock Runtime Converse backend.

Builds the exact Converse request, sends it with botocore retries disabled
(the caller owns retries so every attempt is visible), and returns only the
portable subset of the response.
"""

from __future__ import annotations

import dataclasses
import threading
from typing import Any, Callable, Mapping, Sequence

import botocore

from .credentials import CREDENTIAL_HINT, ProfileTokenSource
from .errors import ErrorInfo, classify_error
from .models import MODEL_REGIONS


class AccessError(Exception):
    """A classified failure. ``kind`` is one of errors.KINDS."""

    def __init__(self, info: ErrorInfo):
        super().__init__(f"{info.error_class}: {info.message}")
        self.kind = info.kind
        self.error_class = info.error_class
        self.code = info.code
        self.http_status = info.http_status
        self.message = info.message


@dataclasses.dataclass
class Reply:
    text: str
    reasoning: list[str]
    redacted_reasoning_blocks: int
    stop_reason: str | None
    usage: dict[str, int | float]
    metrics: dict[str, int | float]
    block_types: list[str]


def _numeric_map(value: Any) -> dict[str, int | float]:
    if not isinstance(value, dict):
        return {}
    return {str(k): v for k, v in value.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}


def parse_converse_response(response: Any) -> Reply:
    """Text blocks are joined into ``text``; reasoning blocks are kept apart."""
    response = response if isinstance(response, dict) else {}
    message = (response.get("output") or {}).get("message") or {}
    texts: list[str] = []
    reasoning: list[str] = []
    redacted = 0
    block_types: list[str] = []
    for block in message.get("content") or []:
        if not isinstance(block, dict):
            continue
        block_types.append(",".join(sorted(block)) or "?")
        if isinstance(block.get("text"), str):
            texts.append(block["text"])
        elif isinstance(block.get("reasoningContent"), dict):
            content = block["reasoningContent"]
            reasoning_text = content.get("reasoningText")
            if isinstance(reasoning_text, dict) and isinstance(reasoning_text.get("text"), str):
                reasoning.append(reasoning_text["text"])
            if "redactedContent" in content:
                redacted += 1
    stop_reason = response.get("stopReason")
    return Reply(
        text="".join(texts),
        reasoning=reasoning,
        redacted_reasoning_blocks=redacted,
        stop_reason=stop_reason if isinstance(stop_reason, str) else None,
        usage=_numeric_map(response.get("usage")),
        metrics=_numeric_map(response.get("metrics")),
        block_types=block_types,
    )


class BedrockConverseBackend:
    name = "bedrock-converse"

    def __init__(
        self,
        token_source: ProfileTokenSource | None = None,
        *,
        connect_timeout: float = 15.0,
        read_timeout: float = 900.0,
        max_pool_connections: int = 64,
        allowlist: Mapping[str, str] = MODEL_REGIONS,
        client_factory: Callable[[str], Any] | None = None,
    ):
        """``client_factory(region)`` replaces the real boto3 client (tests)."""
        self.token_source = token_source if token_source is not None or client_factory else ProfileTokenSource()
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.max_pool_connections = max_pool_connections
        self.allowlist = dict(allowlist)
        self.client_factory = client_factory
        self._clients: dict[str, Any] = {}
        self._lock = threading.Lock()

    @property
    def credential_hint(self) -> str:
        return getattr(self.token_source, "hint", CREDENTIAL_HINT)

    def models(self) -> dict[str, str]:
        return dict(self.allowlist)

    def versions(self) -> dict[str, str]:
        return {"botocore_version": botocore.__version__}

    def client(self, region: str) -> Any:
        with self._lock:
            client = self._clients.get(region)
        if client is not None:
            return client
        if self.client_factory is not None:
            client = self.client_factory(region)
        else:
            from botocore.config import Config

            session = self.token_source.session()
            client = session.client(
                "bedrock-runtime",
                region_name=region,
                config=Config(
                    connect_timeout=self.connect_timeout,
                    read_timeout=self.read_timeout,
                    retries={"total_max_attempts": 1, "mode": "standard"},
                    max_pool_connections=self.max_pool_connections,
                    tcp_keepalive=True,
                    user_agent_extra="batch-runner/1",
                ),
            )
        with self._lock:
            return self._clients.setdefault(region, client)

    def reset(self) -> None:
        """After a credential failure: new Session next time, so credential_process runs again."""
        with self._lock:
            self._clients = {}
        if self.token_source is not None:
            self.token_source.reset()

    def prepare(
        self,
        model: str,
        system: str | None,
        messages: Sequence[tuple[str, str]],
        inference: Mapping[str, Any],
        additional: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if model not in self.allowlist:
            raise ValueError(f"model {model!r} is not allowlisted")
        request: dict[str, Any] = {
            "modelId": model,
            "messages": [{"role": role, "content": [{"text": text}]} for role, text in messages],
            "inferenceConfig": dict(inference),
        }
        if system is not None:
            request["system"] = [{"text": system}]
        if additional:
            request["additionalModelRequestFields"] = dict(additional)
        return request

    def invoke(self, model: str, request: dict[str, Any]) -> Reply:
        if request.get("modelId") != model or model not in self.allowlist:
            raise AccessError(ErrorInfo("invalid", "NotAllowlisted", None, None, "model is not allowlisted"))
        try:
            response = self.client(self.allowlist[model]).converse(**request)
        except Exception as exc:
            raise AccessError(classify_error(exc)) from None
        return parse_converse_response(response)
