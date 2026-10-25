#!/bin/bash
# run_bounded.sh MINUTES cmd [args...]
# Runs cmd in its own session/process group; after MINUTES sends TERM to the whole group (torchrun and all
# ranks, unlike plain `timeout` on a wrapper script), then KILL after 120 s. Returns cmd's exit code, or 124.
MIN=$1; shift
setsid "$@" &
PID=$!
( sleep $((MIN*60)); kill -TERM -- -$PID 2>/dev/null; sleep 120; kill -KILL -- -$PID 2>/dev/null ) &
WD=$!
wait $PID; RC=$?
if kill -0 $WD 2>/dev/null; then kill $WD 2>/dev/null; pkill -P $WD sleep 2>/dev/null; else RC=124; fi
exit $RC
