"""The only thing the runtime knows about model access.

A backend is any object with:

    credential_hint: str
        Short operator instruction shown when credentials fail ("run mwinit").
    models() -> Mapping[str, str]
        Allowlisted model ids -> location label (stored as ``region``).
    prepare(model, system, messages, inference, additional) -> dict
        The exact JSON-serialisable wire request. The runtime hashes it
        (``request_sha256``) and passes it back to ``invoke`` unchanged.
    invoke(model, request) -> reply
        reply has .text (str), .reasoning (list[str]), .redacted_reasoning_blocks
        (int), .stop_reason (str|None), .usage (dict), .metrics (dict).
        On failure raises an exception whose ``.kind`` is one of KINDS
        (optional: .error_class, .code, .http_status, .message). Exceptions
        without a known ``.kind`` are treated as transient.
    reset() -> None
        Forget cached sessions/clients (called before each credential retry).
    versions() -> Mapping[str, str]
        Library versions copied into every raw record (e.g. botocore_version).

Nothing here imports a provider SDK.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Mapping, Protocol, Sequence

THROTTLED = "throttled"
TRANSIENT = "transient"
CREDENTIAL = "credential"
ACCESS_DENIED = "access_denied"
MODEL_UNAVAILABLE = "model_unavailable"
INVALID = "invalid"
KINDS = frozenset({THROTTLED, TRANSIENT, CREDENTIAL, ACCESS_DENIED, MODEL_UNAVAILABLE, INVALID})


class ModelBackend(Protocol):  # structural; for readers and type checkers only
    credential_hint: str

    def models(self) -> Mapping[str, str]: ...

    def prepare(self, model: str, system: str | None, messages: Sequence[tuple[str, str]],
                inference: Mapping[str, Any], additional: Mapping[str, Any] | None) -> dict[str, Any]: ...

    def invoke(self, model: str, request: dict[str, Any]) -> Any: ...

    def reset(self) -> None: ...

    def versions(self) -> Mapping[str, str]: ...


@dataclasses.dataclass
class Failure:
    kind: str
    error_class: str
    code: str | None = None
    http_status: int | None = None
    message: str = ""


def failure_from_exception(exc: BaseException) -> Failure:
    kind = getattr(exc, "kind", None)
    if kind in KINDS:
        return Failure(
            kind=kind,
            error_class=str(getattr(exc, "error_class", None) or type(exc).__name__),
            code=getattr(exc, "code", None),
            http_status=getattr(exc, "http_status", None),
            message=str(getattr(exc, "message", "") or "")[:4000],
        )
    return Failure(TRANSIENT, type(exc).__name__, None, None, str(exc)[:500])
