#!/bin/bash
# Re-run everything that costs nothing and save the output next to the originals (decision 0051). About 40 minutes; needs Docker.
# Originals stay where they are; the new output goes to eval/results/replicated/.
cd "$(dirname "$0")/../.."
R=eval/results/replicated; mkdir -p $R/harness
run() { name=$1; shift; echo "== $name"; "$@" > "$R/$name.txt" 2>&1; echo "exit $? " >> "$R/$name.txt"; }
run bernard_tests_docker uv run -q pytest runtime -q
SANDBOX=subprocess run bernard_tests_subprocess uv run -q pytest runtime -q
run alice_free_tests uv run -q --with anthropic python -m pytest builder web -q
for e in path_guard file_tools output_limit server_start sandbox_compare timeout_choice attacks; do run "$e" uv run -q python "runtime/experiments/$e.py"; done
cp benchmark/validation.json $R/validation_before.json
run validate_all uv run -q python benchmark/validate.py
cp benchmark/validation.json $R/validation_after.json; git checkout -q benchmark/validation.json
run recipes uv run -q python kb/check_recipes.py
cp kb/compare.json $R/compare_before.json
run search_compare uv run -q --extra kb python -m kb.compare
mv kb/compare.json $R/compare_after.json; git checkout -q kb/compare.json
run break_search uv run -q --extra kb python -m kb.break_search
for w in 1 2 4 8 16; do run "workers_$w" uv run -q python -m eval.harness all --references --workers $w --name "rep_workers_$w"; done
run repeat3_w8 uv run -q python -m eval.harness all --references --workers 8 --repeat 3 --name rep_repeat3_w8
run repeat2_w16 uv run -q python -m eval.harness all --references --workers 16 --repeat 2 --name rep_repeat2_w16
mv eval/results/harness/rep_*.json $R/harness/
cp eval/results/harness_failures.json $R/harness_failures_before.json
run harness_failures uv run -q python -m eval.experiments.harness_failures
mv eval/results/harness_failures.json $R/harness_failures_after.json; git checkout -q eval/results/harness_failures.json
run handoff_checks uv run -q python -m eval.experiments.handoff_checks
echo ALL DONE
