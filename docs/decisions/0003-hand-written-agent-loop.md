# 0003. Hand-written ReAct loop and a plain Python orchestrator

- Status: Proposed
- Date: 2026-10-18
- Decided by: —

## Context

The agent is the core of the platform and the viva will ask how it works, step by step.

## Options considered

- An agent framework (LangChain, CrewAI).
- An LLM acting as the "manager" of other agents.
- Our own loop using the LLM's native tool calling, run by a plain Python state machine.

## Decision

Our own ReAct (thought, action, observation) loop with native tool calling, orchestrated by a plain Python state machine.

## Consequences

- Every step is visible and explainable, and gives Section A real material for topics n (ReAct), o (tool use) and r (orchestration).
- Retries, cost caps and step limits are predictable.
- More code to write ourselves than with a framework.
