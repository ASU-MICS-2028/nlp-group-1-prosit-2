#!/bin/bash
# S5.3 and S5.4: build all 15 tasks once per setup, then score each 3 times with the restart check. About $17.
#     bash eval/experiments/ablations.sh          # everything
#     bash eval/experiments/ablations.sh build s53_plan     # one setup's builds
# Builds run 3 setups at a time. Scoring waits for all of them: the harness removes every sandbox container when it starts.
# Results: eval/results/harness/<setup>.json, the builds in eval/results/ablations/<setup>/, logs in eval/results/ablations/logs/.
set -u
UV="uv run --env-file .env --with anthropic"
ASK="--ask 3 --client answers"
ARMS=${ARMS:-"s53_plan s53_noask s53_nottest s53_search s53_split s54_sonnet s54_haiku"}
OUT=eval/results/ablations

if [ "${1:-}" = build ]; then
  a=$2
  case $a in
    s53_plan)    $UV python -m builder plan all $ASK --yes --run $a && $UV python -m builder build all --plan --run $a ;;  # what real clients get
    s53_noask)   $UV python -m builder build all --run $a ;;
    s53_nottest) $UV python -m builder build all $ASK --prompt D --run $a ;;  # prompt D: no "write and run your own tests" step
    s53_search)  $UV --extra kb python -m builder build all $ASK --search --run $a ;;
    s53_split)   $UV python -m builder plan all $ASK --yes --run $a && $UV python -m builder build all --plan --repairs 2 --run $a ;;  # Planner, Builder, Tester
    s54_sonnet*) $UV python -m builder build all $ASK --model claude-sonnet-5-5 --run $a ;;
    s54_haiku)   $UV python -m builder build all $ASK --model claude-haiku-5-5 --run $a ;;
    *) echo "unknown setup $a"; exit 2 ;;
  esac
  exit
fi

mkdir -p $OUT/logs
printf '%s\n' $ARMS | xargs -P 3 -I{} sh -c "bash '$0' build {} > $OUT/logs/{}.log 2>&1; echo 'built {}'"
for a in $ARMS; do
  $UV python -m eval.harness all projects/$a --repeat 3 --restart --name $a > $OUT/logs/${a}_score.log 2>&1
  tail -1 $OUT/logs/${a}_score.log
  for f in projects/$a/*/; do
    t=$(basename "$f"); mkdir -p $OUT/$a/$t
    cp "$f"app.py "$f"ops.json "$f"run.json "$f"questions.json "$f"plan.json "$f"trace.jsonl $OUT/$a/$t/ 2>/dev/null
  done
done
echo finished
