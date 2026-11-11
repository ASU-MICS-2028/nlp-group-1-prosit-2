#!/bin/bash
# S6.1: a brand-new clone from GitHub, only the commands in README, knowledge/environment.md and the learnings files.
S=<scratchpad>   # a temporary folder
BRANCH=${1:-main}   # which branch to clone
OUT=$S/fresh_out/log.txt
: > $OUT
run() { echo "\$ $*" >> $OUT; start=$(date +%s); bash -o pipefail -c "$*" >> $OUT 2>&1; code=$?; echo "-> exit $code, $(( $(date +%s) - start )) s" >> $OUT; echo >> $OUT; }
cd $S && rm -rf $S/fresh
run "date -u; sw_vers -productVersion; uname -m; docker context show; uv --version"
run "git clone -q -b $BRANCH https://github.com/ASU-MICS-2028/nlp-group-1-prosit-2 $S/fresh && cd $S/fresh && git log --oneline -1"
cd $S/fresh
run "git config core.hooksPath .githooks && git config core.hooksPath"
run "uv sync"
run "uv run python -c 'import platform, sys; print(platform.machine(), sys.version.split()[0])'"
run "docker build --no-cache -q -t w2-sandbox runtime/sandbox && docker image ls w2-sandbox --format '{{.Repository}} {{.Size}} {{.CreatedSince}}'"
run "docker pull -q alpine/socat:1.8.0.3"
run "uv run pytest runtime -q 2>&1 | tail -3"
run "SANDBOX=subprocess uv run pytest runtime -q 2>&1 | tail -3"
run "uv run --with anthropic python -m pytest builder web -q 2>&1 | tail -3"
run "uv run python -m pytest eval/tests -q 2>&1 | tail -3"
run "uv run python benchmark/validate.py church_signup; git status --short"
run "uv run python -m eval.harness all --references 2>&1 | tail -4"
run "uv run --extra kb python -m kb.search 'two people booked the same room' 2>&1 | grep -v -i -E 'download|warn|hf_token|redirect' | head -6"
run "uv run python eval/experiments/audit_numbers.py 2>&1 | tail -2"
run "PYTHONPATH=. uv run --with anthropic --with playwright python eval/results/walkthrough/part6/new_page/check_page.py 2>&1 | grep -E 'errors|sideways scroll True|Traceback|Error' ; git status --short | head -5"
# the platform with no key: the page loads, a bad request gets a plain refusal
BUILDS_ROOT=$S/fresh_builds uv run --with anthropic python -m uvicorn web.app:app --host 127.0.0.1 --port 8081 > $S/fresh_out/uvicorn.txt 2>&1 &
P=$!; sleep 6
run "curl -s -o /dev/null -w 'GET / %{http_code}\n' http://127.0.0.1:8081/; curl -s -X POST http://127.0.0.1:8081/api/builds -H 'content-type: application/json' -d '{\"request\": \"\"}'; echo"
kill $P; sleep 1
run "(lsof -i :8081 -i :8090 || true) | wc -l; docker ps --format '{{.Names}}' | grep -v -E 'k3d-' | wc -l"
echo DONE >> $OUT
