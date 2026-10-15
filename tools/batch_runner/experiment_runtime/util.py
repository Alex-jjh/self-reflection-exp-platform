"""Small shared helpers for the runtime."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

LOG = logging.getLogger("batch_runner")

EXIT_OK = 0
EXIT_CRASH = 1
EXIT_CONFIG = 2
EXIT_INCOMPLETE = 3
EXIT_CREDENTIAL_TIMEOUT = 4
EXIT_NEEDS_OPERATOR = 5


class ConfigError(Exception):
    """Bad input or setup; restarting will not help (exit code 2)."""


def setup_logging(level: int = logging.INFO, names: Iterable[str] = ("batch_runner", "bedrock_access")) -> None:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%dT%H:%M:%SZ")
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    for name in names:
        logger = logging.getLogger(name)
        logger.handlers[:] = [handler]
        logger.setLevel(level)
        logger.propagate = False


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def blind_id(salt: str, cell_id: str) -> str:
    """First 16 hex of sha256(salt + cell_id)."""
    return hashlib.sha256((salt + cell_id).encode("utf-8")).hexdigest()[:16]


def order_key(seed: str, cell_id: str) -> str:
    """Fixed-seed shuffle key: stable across runs and independent of file order."""
    return hashlib.sha256(f"{seed}\x00{cell_id}".encode("utf-8")).hexdigest()


def parse_shard(spec: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)/(\d+)", spec.strip())
    if not match:
        raise ConfigError(f"--shard must look like i/n, got {spec!r}")
    index, count = int(match.group(1)), int(match.group(2))
    if count < 1 or not 0 <= index < count:
        raise ConfigError(f"--shard {spec}: need 0 <= i < n")
    return index, count


def in_shard(cell_id: str, shard: tuple[int, int]) -> bool:
    index, count = shard
    if count == 1:
        return True
    return int(hashlib.sha256(cell_id.encode("utf-8")).hexdigest()[:12], 16) % count == index


def source_sha256(paths: Iterable[Path], root: Path) -> str:
    """Hash of the code that produces raw files (path + bytes of each file)."""
    digest = hashlib.sha256()
    for path in sorted(Path(p) for p in paths):
        digest.update(str(path.relative_to(root)).encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def fmt_interval(seconds: float) -> str:
    if seconds >= 60 and abs(seconds / 60 - round(seconds / 60)) < 1e-9:
        return f"{int(round(seconds / 60))} min"
    return f"{seconds:g} s"


def fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days}d{hours:02d}h"
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"
