"""The AI token source: an AWS profile whose credential_process refreshes itself.

Rules (CODEX_BEDROCK_TEMP_CREDENTIAL_RUNBOOK.md):
- one long-lived ``boto3.Session(profile_name="codex-DO-NOT-DELETE")`` so the
  SDK re-runs credential_process before expiry;
- never print, export or write credential values; never touch ``.bedrock_key``;
- a new Session is created only after a credential failure (``reset``), which
  simply makes botocore run credential_process again.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from typing import Any

from .errors import classify_error

PROFILE_NAME = "codex-DO-NOT-DELETE"
CREDENTIAL_HINT = "run mwinit"

LOG = logging.getLogger("bedrock_access")


def scrub_bearer_env() -> list[str]:
    """Remove AWS_BEARER_TOKEN_* from this process so botocore cannot use a
    long-term Bedrock bearer token instead of the profile. Values are never read."""
    removed = [name for name in os.environ if name.startswith("AWS_BEARER_TOKEN_")]
    for name in removed:
        os.environ.pop(name, None)
        LOG.warning("ignoring %s from the environment; authenticating with profile %s only", name, PROFILE_NAME)
    return removed


class ProfileTokenSource:
    """Hands out one cached boto3 Session for an AWS profile."""

    hint = CREDENTIAL_HINT

    def __init__(self, profile_name: str = PROFILE_NAME):
        self.profile_name = profile_name
        self._lock = threading.Lock()
        self._session: Any = None
        self.resets = 0

    def session(self) -> Any:
        import boto3

        with self._lock:
            if self._session is None:
                # An explicit profile also disables botocore's env-var credential provider.
                self._session = boto3.Session(profile_name=self.profile_name)
            return self._session

    def reset(self) -> None:
        with self._lock:
            self._session = None
            self.resets += 1

    def describe(self) -> dict[str, str]:
        return {"type": "aws-profile/credential_process", "profile": self.profile_name}


def caller_identity(source: ProfileTokenSource) -> dict[str, Any]:
    """Account id and role name behind the profile (never credential values)."""
    from botocore.config import Config

    try:
        sts = source.session().client(
            "sts", region_name="us-west-2",
            config=Config(connect_timeout=5, read_timeout=10, retries={"total_max_attempts": 2, "mode": "standard"}),
        )
        identity = sts.get_caller_identity()
    except Exception as error:  # advisory only; Bedrock calls decide
        info = classify_error(error)
        return {"error": info.error_class, "kind": info.kind}
    arn = str(identity.get("Arn", ""))
    match = re.match(r"arn:aws[\w-]*:sts::\d+:assumed-role/([^/]+)/", arn)
    return {"account": identity.get("Account"), "role": match.group(1) if match else None}
