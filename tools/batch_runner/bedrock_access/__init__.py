"""Model access for Bedrock: where the AI credentials come from and how a request
reaches a model.

This package knows nothing about experiments, cells, blinding or resumption.
It does not import ``experiment_runtime``; the two meet only through the small
duck-typed contract documented in ``experiment_runtime/contract.py``:

    backend.credential_hint            -> str shown when credentials fail
    backend.models()                   -> {model_id: location label}
    backend.prepare(model, system, messages, inference, additional) -> wire request (dict)
    backend.invoke(model, request)     -> reply with .text .reasoning .redacted_reasoning_blocks
                                          .stop_reason .usage .metrics
                                          raises an exception carrying .kind (see errors.py)
    backend.reset()                    -> forget sessions/clients after a credential failure
    backend.versions()                 -> {"botocore_version": ...}
"""

from .backend import AccessError, BedrockConverseBackend, Reply, parse_converse_response
from .credentials import PROFILE_NAME, ProfileTokenSource, caller_identity, scrub_bearer_env
from .errors import (
    ACCESS_DENIED,
    CREDENTIAL,
    INVALID,
    KINDS,
    MODEL_UNAVAILABLE,
    THROTTLED,
    TRANSIENT,
    ErrorInfo,
    classify_error,
)
from .models import MODEL_REGIONS, is_anthropic, is_openai

__all__ = [
    "ACCESS_DENIED", "CREDENTIAL", "INVALID", "KINDS", "MODEL_UNAVAILABLE", "THROTTLED", "TRANSIENT",
    "AccessError", "BedrockConverseBackend", "ErrorInfo", "MODEL_REGIONS", "PROFILE_NAME",
    "ProfileTokenSource", "Reply", "caller_identity", "classify_error", "is_anthropic", "is_openai",
    "parse_converse_response", "scrub_bearer_env",
]
