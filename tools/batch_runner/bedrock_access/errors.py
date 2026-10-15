"""Classify Bedrock / botocore failures into a small set of kinds.

The kind strings are the contract with any caller (see
experiment_runtime/contract.py); keep them in sync:

    throttled          capacity: back off and retry, shrink concurrency
    transient          5xx, timeouts, connection errors: retry with a bound
    credential         expired/invalid credentials, credential_process failure
    access_denied      AccessDenied (caller decides: credential vs model access)
    model_unavailable  model id not found in this region
    invalid            this request is wrong for this model: do not retry
"""

from __future__ import annotations

import dataclasses
import re

from botocore import exceptions as bexc

THROTTLED = "throttled"
TRANSIENT = "transient"
CREDENTIAL = "credential"
ACCESS_DENIED = "access_denied"
MODEL_UNAVAILABLE = "model_unavailable"
INVALID = "invalid"
KINDS = frozenset({THROTTLED, TRANSIENT, CREDENTIAL, ACCESS_DENIED, MODEL_UNAVAILABLE, INVALID})

THROTTLE_CODES = {
    "ThrottlingException", "Throttling", "TooManyRequestsException", "ServiceQuotaExceededException",
    "RequestLimitExceeded", "ProvisionedThroughputExceededException", "SlowDown", "RequestThrottled",
    "RequestThrottledException", "LimitExceededException",
}
CREDENTIAL_CODES = {
    "ExpiredTokenException", "ExpiredToken", "UnrecognizedClientException", "InvalidClientTokenId",
    "InvalidSignatureException", "SignatureDoesNotMatch", "IncompleteSignature",
    "MissingAuthenticationToken", "MissingAuthenticationTokenException", "AuthFailure",
    "InvalidAccessKeyId", "InvalidToken", "TokenRefreshRequired", "NotAuthorized",
}
ACCESS_DENIED_CODES = {"AccessDeniedException", "AccessDenied"}
MODEL_UNAVAILABLE_CODES = {"ResourceNotFoundException"}
TRANSIENT_CODES = {
    "InternalServerException", "InternalFailure", "InternalServerError", "InternalError",
    "ServiceUnavailableException", "ServiceUnavailable", "ModelNotReadyException",
    "ModelTimeoutException", "ModelErrorException", "RequestTimeout", "RequestTimeoutException",
    "BadGateway", "GatewayTimeout", "RequestExpired", "ServerError", "ModelStreamErrorException",
}
CREDENTIAL_EXCEPTION_TYPES: tuple[type[BaseException], ...] = (
    bexc.NoCredentialsError,
    bexc.PartialCredentialsError,
    bexc.CredentialRetrievalError,  # credential_process exited non-zero (Midway / Caminus)
    bexc.TokenRetrievalError,
    bexc.SSOError,
    bexc.RefreshWithMFAUnsupportedError,
    bexc.ProfileNotFound,
    bexc.NoAuthTokenError,
    bexc.InvalidConfigError,
)
CONNECTION_EXCEPTION_TYPES: tuple[type[BaseException], ...] = (
    bexc.ConnectionError,
    bexc.HTTPClientError,
    bexc.IncompleteReadError,
    ConnectionError,
    TimeoutError,
    OSError,
)
_CREDENTIAL_HINT_RE = re.compile(r"credential|mwinit|midway|caminus|security token|token (?:has )?expired", re.I)
_THROTTLE_HINT_RE = re.compile(r"too many (?:requests|tokens)|rate exceeded|throttl", re.I)
_KEY_ID_RE = re.compile(r"\b(?:AKIA|ASIA|AROA|AIDA)[A-Z0-9]{12,}\b")
_TOKEN_RE = re.compile(r"(?i)(x-amz-security-token|sessiontoken|secretaccesskey|authorization)([=:]\s*)\S+")


def redact(text: str) -> str:
    """Defensive scrub of anything shaped like an AWS key id or token."""
    text = _KEY_ID_RE.sub("<redacted-key-id>", text)
    return _TOKEN_RE.sub(r"\1\2<redacted>", text)


@dataclasses.dataclass
class ErrorInfo:
    kind: str
    error_class: str
    code: str | None = None
    http_status: int | None = None
    message: str = ""


def classify_error(exc: BaseException) -> ErrorInfo:
    if isinstance(exc, bexc.ClientError):
        error = exc.response.get("Error") or {}
        code = str(error.get("Code") or "") or None
        status = (exc.response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
        status = status if isinstance(status, int) else None
        message = redact(str(error.get("Message") or ""))[:4000]
        error_class = f"ClientError:{code or status}"
        if code in THROTTLE_CODES or status == 429:
            kind = THROTTLED
        elif code in CREDENTIAL_CODES:
            kind = CREDENTIAL
        elif code in ACCESS_DENIED_CODES:
            kind = ACCESS_DENIED
        elif code in MODEL_UNAVAILABLE_CODES:
            kind = MODEL_UNAVAILABLE
        elif code in TRANSIENT_CODES or (status is not None and status >= 500):
            kind = TRANSIENT
        elif status == 401:
            kind = CREDENTIAL
        elif status == 403:
            kind = ACCESS_DENIED
        else:
            kind = INVALID
        if kind == INVALID and _THROTTLE_HINT_RE.search(message):
            kind = THROTTLED
        return ErrorInfo(kind, error_class, code, status, message)

    name = type(exc).__name__
    message = redact(str(exc))[:4000]
    if isinstance(exc, CREDENTIAL_EXCEPTION_TYPES):
        return ErrorInfo(CREDENTIAL, name, None, None, message)
    if isinstance(exc, bexc.ParamValidationError):
        return ErrorInfo(INVALID, name, None, None, message)
    if not isinstance(exc, CONNECTION_EXCEPTION_TYPES) and _CREDENTIAL_HINT_RE.search(message):
        return ErrorInfo(CREDENTIAL, name, None, None, message)
    # connection errors, timeouts and anything unexpected: retried with a bound
    return ErrorInfo(TRANSIENT, name, None, None, message)
