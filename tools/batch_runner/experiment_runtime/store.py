"""All file I/O for one output directory.

    raw/<blind>.json        one per completed cell (the 'done' marker); never overwritten
    failed/<blind>.json     non-retryable failure (retried only with --retry-failed)
    reasoning/<blind>.json  reasoning blocks, if the model returned any (not for coders)
    KEY/salt.txt            random salt, created once
    KEY/map.jsonl           cell_id -> blind
    attempts.jsonl          append-only, one line per attempt, no content
    heartbeat/<shard>.json  live state of a runner
    locks/<shard>.lock      flock held by the active runner of a shard
    tmp/                    staging for atomic writes (same filesystem)

Every file is written to tmp/, fsynced, then published with link() (never
overwrites) or rename() (replace). A crash at any moment leaves either the
complete file or nothing.
"""

from __future__ import annotations

import collections
import errno
import fcntl
import json
import os
import re
import secrets
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from .cells import Cell
from .contract import TRANSIENT
from .util import ConfigError, blind_id, parse_utc


def list_json_stems(directory: Path) -> set[str]:
    try:
        with os.scandir(directory) as entries:
            return {
                entry.name[:-5]
                for entry in entries
                if entry.name.endswith(".json") and not entry.name.startswith(".") and entry.is_file()
            }
    except FileNotFoundError:
        return set()


def _dump(record: dict[str, Any]) -> bytes:
    return json.dumps(record, ensure_ascii=False, indent=1).encode("utf-8") + b"\n"


class OutputStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.raw_dir = self.root / "raw"
        self.failed_dir = self.root / "failed"
        self.reasoning_dir = self.root / "reasoning"
        self.key_dir = self.root / "KEY"
        self.tmp_dir = self.root / "tmp"
        self.heartbeat_dir = self.root / "heartbeat"
        self.locks_dir = self.root / "locks"
        self.attempts_path = self.root / "attempts.jsonl"
        self.salt_path = self.key_dir / "salt.txt"
        self.map_path = self.key_dir / "map.jsonl"
        self._salt: str | None = None
        self._attempt_lock = threading.Lock()
        self._attempt_fd: int | None = None

    # -- primitives ------------------------------------------------------------

    def ensure_dirs(self) -> None:
        for directory in (self.raw_dir, self.failed_dir, self.reasoning_dir, self.key_dir,
                          self.tmp_dir, self.heartbeat_dir, self.locks_dir):
            directory.mkdir(parents=True, exist_ok=True)
        os.chmod(self.key_dir, 0o700)

    def _write_tmp(self, data: bytes) -> str:
        fd, tmp = tempfile.mkstemp(dir=self.tmp_dir, prefix=".w-", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            _unlink(tmp)
            raise
        return tmp

    @staticmethod
    def _fsync_dir(directory: Path) -> None:
        try:
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        except OSError:
            return
        try:
            os.fsync(fd)
        except OSError:
            pass
        finally:
            os.close(fd)

    def publish_exclusive(self, final: Path, data: bytes) -> bool:
        """Atomically create ``final``; never overwrite. False if it already exists."""
        tmp = self._write_tmp(data)
        try:
            try:
                os.link(tmp, final)
            except FileExistsError:
                return False
            except OSError as error:
                if error.errno not in (errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EMLINK, errno.EXDEV):
                    raise
                if final.exists():  # filesystem without hard links: best effort
                    return False
                os.replace(tmp, final)
            self._fsync_dir(final.parent)
            return True
        finally:
            _unlink(tmp)

    def publish_replace(self, final: Path, data: bytes) -> None:
        tmp = self._write_tmp(data)
        try:
            os.replace(tmp, final)
        except BaseException:
            _unlink(tmp)
            raise
        self._fsync_dir(final.parent)

    @staticmethod
    def _append_bytes(path: Path, data: bytes, fsync: bool = False) -> None:
        fd = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            size = os.fstat(fd).st_size
            if size and os.pread(fd, 1, size - 1) != b"\n":
                data = b"\n" + data  # a crash cut the last line short; start a fresh line
            os.write(fd, data)
            if fsync:
                os.fsync(fd)
        finally:
            os.close(fd)

    def cleanup_tmp(self, older_than: float = 3600.0) -> None:
        cutoff = time.time() - older_than
        try:
            with os.scandir(self.tmp_dir) as entries:
                for entry in entries:
                    try:
                        if entry.is_file() and entry.stat().st_mtime < cutoff:
                            os.unlink(entry.path)
                    except FileNotFoundError:
                        pass
        except FileNotFoundError:
            pass

    # -- KEY ---------------------------------------------------------------------

    def load_salt(self, create: bool) -> str | None:
        if self._salt is not None:
            return self._salt
        if not self.salt_path.exists():
            if not create:
                return None
            if self.map_path.exists() or list_json_stems(self.raw_dir) or list_json_stems(self.failed_dir):
                raise ConfigError(
                    f"{self.salt_path} is missing but outputs already exist; refusing to create a new salt "
                    "(every blind id would change). Restore KEY/salt.txt from backup."
                )
            tmp = self._write_tmp((secrets.token_hex(32) + "\n").encode("ascii"))
            try:
                try:
                    os.link(tmp, self.salt_path)  # first writer wins, even with concurrent shards
                except FileExistsError:
                    pass
                else:
                    self._fsync_dir(self.key_dir)
            finally:
                _unlink(tmp)
        salt = self.salt_path.read_text(encoding="ascii").strip()
        if not re.fullmatch(r"[0-9a-f]{64}", salt):
            raise ConfigError(f"{self.salt_path} is malformed")
        self._salt = salt
        return salt

    def sync_map(self, cells: Iterable[Cell]) -> dict[str, str]:
        """cell_id -> blind for all cells; appends new pairs to KEY/map.jsonl."""
        salt = self.load_salt(create=True)
        assert salt is not None
        computed: dict[str, str] = {}
        owner: dict[str, str] = {}
        for cell in cells:
            blind = blind_id(salt, cell.cell_id)
            if owner.setdefault(blind, cell.cell_id) != cell.cell_id:
                raise ConfigError("blind id collision between two cell ids; rename one of them")
            computed[cell.cell_id] = blind
        with open(self.key_dir / "map.lock", "a") as lock_handle:
            fcntl.flock(lock_handle, fcntl.LOCK_EX)
            existing: dict[str, str] = {}
            if self.map_path.exists():
                with self.map_path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        try:
                            record = json.loads(line)
                            existing[record["cell_id"]] = record["blind"]
                        except (json.JSONDecodeError, KeyError, TypeError):
                            continue
            for cell_id, blind in computed.items():
                if cell_id in existing and existing[cell_id] != blind:
                    raise ConfigError("KEY/map.jsonl disagrees with KEY/salt.txt (the salt changed); stop and restore it")
            new_ids = [cell_id for cell_id in computed if cell_id not in existing]
            if new_ids:
                data = "".join(
                    json.dumps({"cell_id": cell_id, "blind": computed[cell_id]}, ensure_ascii=False) + "\n"
                    for cell_id in new_ids
                ).encode("utf-8")
                self._append_bytes(self.map_path, data, fsync=True)
        return computed

    # -- results -------------------------------------------------------------------

    def raw_path(self, blind: str) -> Path:
        return self.raw_dir / f"{blind}.json"

    def failed_path(self, blind: str) -> Path:
        return self.failed_dir / f"{blind}.json"

    def done_blinds(self) -> set[str]:
        return list_json_stems(self.raw_dir)

    def failed_blinds(self) -> set[str]:
        return list_json_stems(self.failed_dir)

    def write_raw(self, blind: str, record: dict[str, Any]) -> bool:
        return self.publish_exclusive(self.raw_path(blind), _dump(record))

    def write_failed(self, blind: str, record: dict[str, Any]) -> None:
        self.publish_replace(self.failed_path(blind), _dump(record))

    def clear_failed(self, blind: str) -> None:
        _unlink(self.failed_path(blind))

    def write_reasoning(self, blind: str, record: dict[str, Any]) -> None:
        self.publish_replace(self.reasoning_dir / f"{blind}.json", _dump(record))

    # -- attempts.jsonl --------------------------------------------------------------

    def append_attempt(self, record: dict[str, Any]) -> None:
        line = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        with self._attempt_lock:
            if self._attempt_fd is None:
                fd = os.open(self.attempts_path, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o600)
                size = os.fstat(fd).st_size
                if size and os.pread(fd, 1, size - 1) != b"\n":
                    os.write(fd, b"\n")
                self._attempt_fd = fd
            os.write(self._attempt_fd, line)  # one O_APPEND write per line

    def close(self) -> None:
        with self._attempt_lock:
            if self._attempt_fd is not None:
                try:
                    os.fsync(self._attempt_fd)
                except OSError:
                    pass
                os.close(self._attempt_fd)
                self._attempt_fd = None

    def iter_attempts(self) -> Iterable[dict[str, Any]]:
        if not self.attempts_path.exists():
            return
        with self.attempts_path.open("rb") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if isinstance(record, dict):
                    yield record

    def attempt_history(self) -> dict[str, list[int]]:
        """blind -> [attempts so far, transient failures so far] (all runs)."""
        history: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
        for record in self.iter_attempts():
            blind = record.get("blind")
            if not isinstance(blind, str):
                continue
            entry = history[blind]
            entry[0] += 1
            if record.get("status") == TRANSIENT:
                entry[1] += 1
        return dict(history)

    def attempts_since(self, cutoff: datetime, margin: timedelta = timedelta(minutes=15)) -> list[dict[str, Any]]:
        """Records with utc >= cutoff, reading the (possibly large) log backwards."""
        if not self.attempts_path.exists():
            return []
        found: list[dict[str, Any]] = []
        stop_before = cutoff - margin

        def consume(line: bytes) -> bool:
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return False
            when = parse_utc(record.get("utc")) if isinstance(record, dict) else None
            if when is None:
                return False
            if when >= cutoff:
                found.append(record)
            return when < stop_before

        with self.attempts_path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            position = handle.tell()
            carry = b""
            finished = False
            while position > 0 and not finished:
                step = min(1 << 20, position)
                position -= step
                handle.seek(position)
                carry = handle.read(step) + carry
                lines = carry.split(b"\n")
                carry = lines[0]
                for line in reversed(lines[1:]):
                    if line.strip() and consume(line):
                        finished = True
            if not finished and carry.strip():
                consume(carry)
        found.reverse()
        return found

    # -- locks and heartbeat -------------------------------------------------------

    def lock_run(self, name: str) -> int:
        path = self.locks_dir / f"{name}.lock"
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise ConfigError(f"another runner is already active for this shard ({path})")
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n".encode("ascii"))
        return fd

    def held_locks(self) -> list[str]:
        held = []
        for path in sorted(self.locks_dir.glob("*.lock")) if self.locks_dir.exists() else []:
            try:
                fd = os.open(path, os.O_RDONLY)
            except OSError:
                continue
            try:
                fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
            except BlockingIOError:
                held.append(path.stem)
            finally:
                os.close(fd)
        return held

    def write_heartbeat(self, name: str, record: dict[str, Any]) -> None:
        self.publish_replace(self.heartbeat_dir / f"{name}.json", _dump(record))

    def read_heartbeats(self) -> list[dict[str, Any]]:
        beats = []
        for stem in sorted(list_json_stems(self.heartbeat_dir)):
            try:
                beats.append(json.loads((self.heartbeat_dir / f"{stem}.json").read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return beats


def _unlink(path: str | Path) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
