#!/usr/bin/env python3
"""Resumable batch runner for Bedrock Converse reply collection.

    runner.py run    --cells F --out DIR [...]   collect replies (resumable)
    runner.py status --cells F --out DIR          done/failed/pending, throughput, ETA
    runner.py probe  --out DIR                    request-format and parameter checks
    runner.py ramp   --out DIR                    concurrency ramp per model

This file is the only place that joins the two packages:
    bedrock_access/      AI token source (codex profile) + Bedrock Converse access
    experiment_runtime/  cells, blinding, resumable store, AIMD, credential pause, status
Neither package imports the other. See README.md.
"""

from __future__ import annotations

import argparse
import collections
import logging
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from bedrock_access import (  # noqa: E402  (token source + model access)
    PROFILE_NAME,
    BedrockConverseBackend,
    ProfileTokenSource,
    caller_identity,
    scrub_bearer_env,
)
from experiment_runtime.engine import RunConfig, install_signal_handlers, prepare_run  # noqa: E402
from experiment_runtime.status import compute_status, print_status  # noqa: E402
from experiment_runtime.util import (  # noqa: E402
    EXIT_CONFIG,
    LOG,
    ConfigError,
    parse_shard,
    setup_logging,
    source_sha256,
)

# Hash of every file that shapes a raw record (diagnostics.py and tests excluded).
CODE_FILES = [
    HERE / "runner.py",
    *sorted((HERE / "experiment_runtime").glob("*.py")),
    *[path for path in sorted((HERE / "bedrock_access").glob("*.py")) if path.name != "diagnostics.py"],
]
CODE_SHA256 = source_sha256(CODE_FILES, HERE)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="runner.py", description="Resumable Bedrock Converse batch runner")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="collect replies (resumable; rerun the same command to resume)")
    run.add_argument("--cells", required=True, type=Path)
    run.add_argument("--out", required=True, type=Path)
    run.add_argument("--max-concurrency-per-model", type=int, default=8)
    run.add_argument("--initial-concurrency", type=int, default=2, help="AIMD starting limit per model")
    run.add_argument("--aimd-increase-after", type=int, default=10,
                     help="consecutive successes before a model's limit grows by 1")
    run.add_argument("--shard", default="0/1", help="i/n: only cells whose sha256(cell_id) mod n == i")
    run.add_argument("--limit", type=int, help="at most N pending cells this run (in interleaved order)")
    run.add_argument("--seed", default="0", help="fixed shuffle seed for the interleaved order")
    run.add_argument("--models", help="comma-separated subset of allowlisted models")
    run.add_argument("--retry-failed", action="store_true", help="also retry cells recorded in failed/")
    run.add_argument("--max-transient-retries", type=int, default=8,
                     help="consecutive 5xx/timeout retries before a cell moves to the back of its queue")
    run.add_argument("--max-cell-transient-failures", type=int, default=40,
                     help="total 5xx/timeout failures of one cell (all runs) before it goes to failed/")
    run.add_argument("--invalid-breaker", type=int, default=20,
                     help="consecutive non-retryable errors that disable a model for this run")
    run.add_argument("--backoff-base", type=float, default=2.0)
    run.add_argument("--backoff-cap", type=float, default=120.0)
    run.add_argument("--credential-retry-interval", type=float, default=300.0)
    run.add_argument("--credential-max-wait", type=float, default=86400.0)
    run.add_argument("--shutdown-timeout", type=float, default=600.0,
                     help="seconds to wait for in-flight calls after SIGTERM/SIGINT")
    run.add_argument("--progress-interval", type=float, default=60.0)
    run.add_argument("--connect-timeout", type=float, default=15.0)
    run.add_argument("--read-timeout", type=float, default=900.0)
    run.add_argument("--expect-role", default="CaminusBedrockAccess",
                     help="stop if the profile's role name does not contain this ('' skips the check)")

    status = sub.add_parser("status", help="progress per model")
    status.add_argument("--cells", required=True, type=Path)
    status.add_argument("--out", required=True, type=Path)
    status.add_argument("--json", action="store_true")
    status.add_argument("--verify", action="store_true",
                        help="also re-hash the request of every done cell against the cells file")

    probe = sub.add_parser("probe", help="tiny real calls: formats and parameters per model")
    probe.add_argument("--out", required=True, type=Path)
    probe.add_argument("--models", help="comma-separated subset")

    ramp = sub.add_parser("ramp", help="concurrency ramp per model (metadata only)")
    ramp.add_argument("--out", required=True, type=Path)
    ramp.add_argument("--models", help="comma-separated subset")
    ramp.add_argument("--steps", default="1,2,4,8,16")
    ramp.add_argument("--calls-per-step", type=int, default=10)
    ramp.add_argument("--max-tokens", type=int, default=300)
    ramp.add_argument("--sequential", action="store_true", help="ramp one model at a time")
    ramp.add_argument("--gpt-additional", help="JSON additionalModelRequestFields for GPT models")
    ramp.add_argument("--claude-additional", help="JSON additionalModelRequestFields for Claude models")
    return parser


def make_backend(connect_timeout: float = 15.0, read_timeout: float = 900.0,
                 max_pool_connections: int = 64) -> BedrockConverseBackend:
    return BedrockConverseBackend(
        ProfileTokenSource(PROFILE_NAME),
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        max_pool_connections=max_pool_connections,
    )


def cmd_run(args: argparse.Namespace) -> int:
    scrub_bearer_env()
    cfg = RunConfig(
        cells_path=args.cells,
        out_dir=args.out,
        max_concurrency=args.max_concurrency_per_model,
        initial_concurrency=args.initial_concurrency,
        increase_after=args.aimd_increase_after,
        shard=parse_shard(args.shard),
        limit=args.limit,
        seed=args.seed,
        models={m.strip() for m in args.models.split(",") if m.strip()} if args.models else None,
        retry_failed=args.retry_failed,
        backoff_base=args.backoff_base,
        backoff_cap=args.backoff_cap,
        max_transient_retries=args.max_transient_retries,
        max_cell_transient_failures=args.max_cell_transient_failures,
        invalid_breaker=args.invalid_breaker,
        credential_retry_interval=args.credential_retry_interval,
        credential_max_wait=args.credential_max_wait,
        shutdown_timeout=args.shutdown_timeout,
        progress_interval=args.progress_interval,
        code_sha256=CODE_SHA256,
    )
    probe_backend = make_backend()
    per_region = collections.Counter(probe_backend.models().values())
    backend = make_backend(args.connect_timeout, args.read_timeout,
                           max(10, max(per_region.values()) * cfg.max_concurrency + 4))
    LOG.info("batch_runner run pid=%d code_sha256=%s %s token_source=%s", os.getpid(), CODE_SHA256[:16],
             backend.versions(), backend.token_source.describe())
    if args.expect_role:
        identity = caller_identity(backend.token_source)
        if "error" in identity:
            LOG.warning("could not read caller identity (%s); continuing, Bedrock calls will decide",
                        identity["error"])
        else:
            LOG.info("identity account=%s role=%s", identity.get("account"), identity.get("role"))
            if args.expect_role not in str(identity.get("role")):
                raise ConfigError(f"profile role {identity.get('role')!r} does not contain {args.expect_role!r}; "
                                  "stopping, as the credential runbook requires")
    runner = prepare_run(cfg, backend)
    install_signal_handlers(runner)
    code = runner.run()
    if runner.abandoned_threads:  # calls still blocked in the SDK: do not wait for them
        logging.shutdown()
        sys.stdout.flush()
        os._exit(code)
    return code


def cmd_status(args: argparse.Namespace) -> int:
    import json

    backend = make_backend()  # models() and prepare() need no credentials
    status = compute_status(args.cells, args.out, backend.models(),
                            prepare=backend.prepare if args.verify else None)
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=1))
    else:
        print_status(status)
    return 0


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            return cmd_run(args)
        if args.command == "status":
            return cmd_status(args)
        from bedrock_access import diagnostics

        scrub_bearer_env()
        if args.command == "probe":
            return diagnostics.cmd_probe(args, make_backend(read_timeout=300.0))
        if args.command == "ramp":
            return diagnostics.cmd_ramp(args, make_backend(read_timeout=300.0, max_pool_connections=100))
    except ConfigError as error:
        LOG.error("%s", error)
        return EXIT_CONFIG
    return EXIT_CONFIG


if __name__ == "__main__":
    sys.exit(main())
