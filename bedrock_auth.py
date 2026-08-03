"""Bedrock auth: load the long-term API key from .bedrock_key (gitignored).

Why a file and not the environment: the host machine carries multiple AWS
credential sets for other work; a file keeps the study credential explicit,
isolated, and rotation-checkable. The key is exported as
AWS_BEARER_TOKEN_BEDROCK, which boto3 (>=1.39.9) uses for bedrock-runtime
only — it does not interact with AWS_ACCESS_KEY_ID / AWS_PROFILE / SSO
credentials that may also be present.

The study account's key policy requires rotation EVERY 7 DAYS;
key_age_days() lets the UI surface a warning before expiry bites
mid-session.
"""

import datetime
import os
from pathlib import Path

KEY_FILE = Path(__file__).resolve().parent / ".bedrock_key"
ROTATION_DAYS = 7
WARN_AFTER_DAYS = 6


def load_bedrock_key() -> bool:
    """Read .bedrock_key and export AWS_BEARER_TOKEN_BEDROCK.

    Returns True if a key was loaded. Falls back silently to the default
    AWS credential chain if the file is absent (dev machines).
    """
    if not KEY_FILE.exists():
        return False
    for line in KEY_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and line != "PASTE-KEY-HERE":
            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = line
            return True
    return False


def key_age_days() -> float | None:
    """Days since .bedrock_key was last modified; None if absent."""
    if not KEY_FILE.exists():
        return None
    mtime = datetime.datetime.fromtimestamp(KEY_FILE.stat().st_mtime)
    return (datetime.datetime.now() - mtime).total_seconds() / 86400


def key_status() -> str:
    """One-line status for the facilitator sidebar / CLI banner."""
    age = key_age_days()
    if age is None:
        return "⚠️ .bedrock_key 不存在 — 使用默认 AWS 凭证链"
    if age >= ROTATION_DAYS:
        return f"🔴 Bedrock key 已 {age:.1f} 天未更新（7 天必须轮换）— 先换 key 再开 session！"
    if age >= WARN_AFTER_DAYS:
        return f"🟡 Bedrock key 已 {age:.1f} 天 — 明天到期，session 前请更新"
    return f"🟢 Bedrock key 正常（{age:.1f} 天 / 7 天）"
