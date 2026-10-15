#!/usr/bin/env bash
# Supervisor for `runner.py run`: restarts it whenever it exits abnormally.
#
# Start (keeps running after you log out; everything is logged to DIR/logs/run_forever.log):
#   cd /home/alexjia/.workspace/self-reflection-exp-platform
#   nohup tools/batch_runner/run_forever.sh --cells /path/cells.jsonl --out /path/DIR >/dev/null 2>&1 &
# Follow the log:
#   tail -F /path/DIR/logs/run_forever.log
# Progress:
#   .venv/bin/python tools/batch_runner/runner.py status --cells /path/cells.jsonl --out /path/DIR
# Stop gracefully (in-flight calls finish, nothing is lost):
#   kill "$(cat /path/DIR/run_forever.pid)"
#
# Any extra options are passed to `runner.py run` unchanged (e.g. --max-concurrency-per-model 8).
#
# Exit code of `runner.py run`              supervisor
#   0        every selected cell is done or in failed/         stop
#   2        configuration error (cells file, lock, role)      stop
#   5        a model was disabled (access / validation)        stop: fix, then start again
#   130/143  runner stopped by SIGINT/SIGTERM                  stop
#   1 crash, 3 incomplete, 4 credentials failed for 24 h,
#   137 killed (e.g. OOM), anything else                       restart after 30 s, doubling to 10 min
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY="${BATCH_RUNNER_PYTHON:-$REPO/.venv/bin/python}"
FIRST_DELAY="${BATCH_RUNNER_RESTART_DELAY:-30}"

OUT=""
prev=""
for arg in "$@"; do
  case "$arg" in --out=*) OUT="${arg#--out=}" ;; esac
  [ "$prev" = "--out" ] && OUT="$arg"
  prev="$arg"
done
if [ -z "$OUT" ]; then
  echo "usage: $0 --cells FILE --out DIR [run options]" >&2
  exit 2
fi
mkdir -p "$OUT/logs"
LOG="$OUT/logs/run_forever.log"
exec >>"$LOG" 2>&1

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

exec 9>"$OUT/run_forever.lock"
if ! flock -n 9; then
  echo "$(ts) supervisor: another supervisor is already running for $OUT; exiting"
  exit 2
fi
echo $$ >"$OUT/run_forever.pid"
trap 'rm -f "$OUT/run_forever.pid"' EXIT

stop=0
child=""
on_signal() {
  stop=1
  echo "$(ts) supervisor: stop requested; asking the runner to finish in-flight calls"
  [ -n "$child" ] && kill -TERM "$child" 2>/dev/null
}
trap on_signal TERM INT

delay=$FIRST_DELAY
while :; do
  started=$(date +%s)
  echo "$(ts) supervisor: starting runner.py run $*"
  "$PY" "$HERE/runner.py" run "$@" &
  child=$!
  wait "$child"
  rc=$?
  while kill -0 "$child" 2>/dev/null; do  # wait was interrupted by our trap: wait for the real exit
    wait "$child"
    rc=$?
  done
  child=""
  ran=$(($(date +%s) - started))
  echo "$(ts) supervisor: runner exited rc=$rc after ${ran}s"
  if [ "$stop" = 1 ]; then
    echo "$(ts) supervisor: stopped on request"
    exit 0
  fi
  case "$rc" in
    0) echo "$(ts) supervisor: all selected cells are done (see failed/ for non-retryable ones)"; exit 0 ;;
    2) echo "$(ts) supervisor: configuration error; not restarting"; exit 2 ;;
    5) echo "$(ts) supervisor: a model was disabled (see MODEL DISABLED above); fix it, then start again"; exit 5 ;;
    130 | 143) echo "$(ts) supervisor: runner was stopped by a signal; not restarting"; exit 0 ;;
  esac
  [ "$ran" -gt 600 ] && delay=$FIRST_DELAY
  echo "$(ts) supervisor: restarting in ${delay}s"
  sleep "$delay" &
  child=$!
  wait "$child"
  child=""
  if [ "$stop" = 1 ]; then
    echo "$(ts) supervisor: stopped on request"
    exit 0
  fi
  delay=$((delay * 2 > 600 ? 600 : delay * 2))
done
