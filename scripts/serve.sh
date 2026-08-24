#!/usr/bin/env bash
# Zara local service.
#
#   scripts/serve.sh start|stop|restart|status|logs
#
# Always launches from ./venv/bin/python. A Streamlit started with the system
# Python was found running for 22h against stale code, which is exactly the
# failure this script exists to prevent: `status` prints the git SHA the
# process was launched at, so "am I testing old code?" is answerable.
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
ROOT="$PWD"

PORT="${ZARA_PORT:-8501}"
PY="$ROOT/venv/bin/python"
LOG_DIR="$ROOT/var/logs"
LOG="$LOG_DIR/app.log"
RUN_DIR="$ROOT/var/run"
PID_FILE="$RUN_DIR/zara.pid"
SHA_FILE="$RUN_DIR/zara.sha"
MAX_LOG_BYTES=$((5 * 1024 * 1024))

mkdir -p "$LOG_DIR" "$RUN_DIR"

die() { echo "error: $*" >&2; exit 1; }

# PID of our supervisor, if it is actually alive.
running_pid() {
  [ -f "$PID_FILE" ] || return 1
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null)" || return 1
  [ -n "$pid" ] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  echo "$pid"
}

# Anything at all bound to the port, ours or not.
port_pids() { lsof -ti:"$PORT" 2>/dev/null; }

port_healthy() {
  curl -sf -o /dev/null --max-time 3 "http://localhost:$PORT/_stcore/health" 2>/dev/null
}

# Identity of the code on disk: HEAD plus a digest of uncommitted changes.
# Comparing SHAs alone is not enough -- most iteration happens in the working
# tree, and a process launched before an uncommitted edit is just as stale as
# one launched before a commit. Streamlit re-executes app.py per interaction
# but keeps zara/* in sys.modules, so engine edits need a restart either way.
code_identity() {
  local sha diff
  sha="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  diff="$(git -C "$ROOT" diff HEAD 2>/dev/null | shasum | cut -c1-8)"
  if git -C "$ROOT" diff --quiet HEAD 2>/dev/null; then
    echo "$sha"
  else
    echo "$sha+wip.$diff"
  fi
}

rotate_log() {
  [ -f "$LOG" ] || return 0
  local size
  size="$(wc -c <"$LOG" 2>/dev/null | tr -d ' ')"
  [ -n "$size" ] && [ "$size" -gt "$MAX_LOG_BYTES" ] || return 0
  mv "$LOG" "$LOG.$(date +%Y%m%d-%H%M%S)"
  # Keep the five most recent rotations.
  ls -1t "$LOG".* 2>/dev/null | tail -n +6 | while read -r old; do rm -f "$old"; done
}

# Supervisor loop: restart Streamlit if it dies, but stop on clean exit
# and back off if it is crash-looping.
supervise() {
  local fails=0
  while true; do
    "$PY" -m streamlit run app.py \
      --server.port "$PORT" \
      --server.headless true \
      --server.fileWatcherType none \
      --browser.gatherUsageStats false >>"$LOG" 2>&1
    local rc=$?
    if [ "$rc" -eq 0 ]; then
      echo "[serve] streamlit exited cleanly, supervisor stopping" >>"$LOG"
      break
    fi
    fails=$((fails + 1))
    if [ "$fails" -ge 5 ]; then
      echo "[serve] streamlit failed $fails times, giving up (see errors above)" >>"$LOG"
      break
    fi
    echo "[serve] streamlit exited rc=$rc, restarting in 3s (failure $fails/5)" >>"$LOG"
    sleep 3
  done
  rm -f "$PID_FILE"
}

cmd_start() {
  [ -x "$PY" ] || die "no venv python at $PY"
  [ -f "$ROOT/app.py" ] || die "app.py not found in $ROOT"

  if pid="$(running_pid)"; then
    echo "already running (pid $pid) on port $PORT — use 'restart' to pick up code changes"
    return 0
  fi

  # A foreign process on the port (e.g. the stale system-Python instance).
  local foreign
  foreign="$(port_pids)"
  if [ -n "$foreign" ]; then
    echo "port $PORT held by a process we did not start:"
    for p in $foreign; do
      ps -o pid=,etime=,command= -p "$p" 2>/dev/null | cut -c1-120 | sed 's/^/  /'
    done
    read -r -p "kill it and take the port? [y/N] " ans
    case "$ans" in
      [yY]*) ;;
      *) die "refusing to double-bind port $PORT" ;;
    esac
    for p in $foreign; do kill "$p" 2>/dev/null; done
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      [ -z "$(port_pids)" ] && break
      sleep 0.5
    done
    for p in $(port_pids); do kill -9 "$p" 2>/dev/null; done
    [ -z "$(port_pids)" ] || die "could not free port $PORT"
    echo "port $PORT freed"
  fi

  rotate_log

  code_identity >"$SHA_FILE"

  {
    echo
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') starting zara @ $(cat "$SHA_FILE") on port $PORT ==="
  } >>"$LOG"

  # GROQ_API_KEY: a stale 7-char placeholder in the shell shadows the real key
  # from .env.local, because dotenv does not override an already-set env var.
  # Unset it here so .env.local always wins (CLAUDE.md, environment gotchas).
  (
    cd "$ROOT" || exit 1
    export PYTHONPATH="$ROOT"
    unset GROQ_API_KEY
    supervise
  ) &
  local sup=$!
  echo "$sup" >"$PID_FILE"
  disown "$sup" 2>/dev/null || true

  printf "starting"
  for _ in $(seq 1 40); do
    if port_healthy; then
      echo
      cmd_status
      echo
      echo "  open http://localhost:$PORT"
      return 0
    fi
    kill -0 "$sup" 2>/dev/null || { echo; die "supervisor died — tail of $LOG:
$(tail -20 "$LOG")"; }
    printf "."
    sleep 0.5
  done
  echo
  echo "did not become healthy within 20s — tail of $LOG:" >&2
  tail -20 "$LOG" >&2
  return 1
}

cmd_stop() {
  local stopped=0
  if pid="$(running_pid)"; then
    # Kill the supervisor first so it does not resurrect Streamlit.
    kill "$pid" 2>/dev/null
    stopped=1
  fi
  rm -f "$PID_FILE"
  for p in $(port_pids); do kill "$p" 2>/dev/null; stopped=1; done
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    [ -z "$(port_pids)" ] && break
    sleep 0.5
  done
  for p in $(port_pids); do kill -9 "$p" 2>/dev/null; done
  [ "$stopped" -eq 1 ] && echo "stopped" || echo "not running"
}

cmd_status() {
  local pid
  if pid="$(running_pid)"; then
    local et
    et="$(ps -o etime= -p "$pid" 2>/dev/null | tr -d ' ')"
    echo "  status   running (supervisor pid $pid, uptime ${et:-?})"
  elif [ -n "$(port_pids)" ]; then
    echo "  status   port $PORT bound by a process we did not start:"
    for p in $(port_pids); do
      ps -o pid=,etime=,command= -p "$p" 2>/dev/null | cut -c1-110 | sed 's/^/           /'
    done
  else
    echo "  status   not running"
    return 1
  fi
  echo "  port     $PORT ($(port_healthy && echo healthy || echo 'not responding'))"
  local launched current
  launched="$( [ -f "$SHA_FILE" ] && cat "$SHA_FILE" || echo unknown )"
  current="$(code_identity)"
  echo "  launched $launched"
  echo "  on disk  $current"
  if [ "$launched" != "$current" ]; then
    echo "  WARNING  code on disk has changed since launch — run 'restart' to serve it"
  fi
  echo "  log      $LOG"
}

case "${1:-status}" in
  start)   cmd_start ;;
  stop)    cmd_stop ;;
  restart) cmd_stop; sleep 1; cmd_start ;;
  status)  cmd_status ;;
  logs)    tail -f "$LOG" ;;
  *)       die "usage: scripts/serve.sh start|stop|restart|status|logs" ;;
esac
