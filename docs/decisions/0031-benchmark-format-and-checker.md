# 0031. Benchmark tasks are checked for being too weak, too strict and flaky before anything is measured

- Status: Accepted
- Date: 2026-10-27
- Decided by: Joseph

## Context

Every later result (the baseline, Alice's agent, the ablations) is measured with the benchmark. A test that fails a correct backend, or passes a broken one, would make every number wrong without anyone noticing.

## Options considered

- Trust each task once its reference passes.
- Check every task automatically: a reference must pass, a second correct backend with other valid choices must pass, and deliberately broken copies (mutants) must fail.

## Decision

Each task has `request.md` (only what the user would type), `task.json` (tier, vague; never shown to the agent), `operations.json`, hidden tests, a reference backend with its own names, 3–5 mutants, `answers.json` and `client_brief.md`; 6 tasks also have `reference_b`. `benchmark/validate.py` starts every backend in Bernard's sandbox and requires: the reference passes twice on the same server and once in reverse order, `reference_b` passes, every mutant fails at least one test, at least 8 tests. It records which tests catch each mutant.

## Consequences

- The checker was itself tested on 5 deliberately bad tasks and flagged all 5.
- All 15 tasks pass: 192 tests, 75/75 mutants caught, 6/6 second backends pass, identical results on a second full run (no flaky tests). A full check takes about 77 s.
- The test helper translates field names at every depth with one map per operation, so a backend that reuses one name for two different things at different depths cannot be mapped. No task does this.
