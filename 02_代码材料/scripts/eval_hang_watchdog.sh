#!/bin/bash
# eval_hang_watchdog.sh EVAL_TAG [SILENT_SEC=900]
# Rides on the eval job (srun --overlap). Every 2 min: for every task of every setting that is still < 100 episodes,
# if its per-task eval log has been silent for > SILENT_SEC, kill that task's sim process (the launcher restarts it;
# the client's crash-resume records the hung episode as a crash/failure and continues with the next seed).
# Patterns use the [x] trick so pgrep/pkill never match this script's own command line.
TAG=$1; SIL=${2:-900}; E=/path/to/lingbot/eval/$TAG
while true; do
  for set in clean randomized; do
    for lg in $E/$set/run/eval_logs/*.log; do
      [ -f "$lg" ] || continue; t=$(basename $lg .log); f=$E/$set/run/eval_results/$t/lb_resume.jsonl
      [ -f $f ] && [ $(grep -c . $f) -ge 100 ] && continue
      age=$(( $(date +%s) - $(stat -c %Y $lg) ))
      if [ $age -gt $SIL ]; then
        pids=$(pgrep -f "[e]val_policy_client_lingbotvla.py .*--task_name $t --task_config demo_$set")
        [ -n "$pids" ] && { echo "$(date +%T) $set/$t log silent ${age}s -> killing sim $pids"; kill -9 $pids; }
      fi
    done
  done
  sleep 120
done
