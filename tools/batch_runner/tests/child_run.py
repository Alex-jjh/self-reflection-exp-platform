"""Runs the real engine with a slow fake client in a separate process, so a
test can SIGKILL or SIGTERM it mid-run.

usage: child_run.py CELLS OUT DELAY_SECONDS
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import FakeBedrockClient, fake_backend, fast_config, ok_response  # noqa: E402

from experiment_runtime.engine import install_signal_handlers, prepare_run  # noqa: E402
from experiment_runtime.util import setup_logging  # noqa: E402


def main() -> int:
    cells, out, delay = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3])
    setup_logging()

    def behaviour(call):
        time.sleep(delay)
        return ok_response(f"reply for {call.cell_id} " + "x" * 2000)

    backend, _ = fake_backend(FakeBedrockClient(behaviour))
    runner = prepare_run(fast_config(cells, out, shutdown_timeout=20.0), backend)
    install_signal_handlers(runner)
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
