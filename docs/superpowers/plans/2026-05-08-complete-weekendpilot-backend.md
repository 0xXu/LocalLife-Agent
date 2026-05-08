# WeekendPilot Complete Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the complete local backend from `detailed_design.md` without modifying the existing frontend.

**Architecture:** Use a central deterministic state-machine orchestrator with LLM-assisted intent parsing, local MCP-ready tool adapters, durable in-memory checkpoints, trace records, confirmation gates, and recovery flows. External business APIs are represented by replaceable local adapters that return realistic receipts.

**Tech Stack:** Python 3.11+ stdlib, dataclasses, `http.server`, local JSON-compatible generated catalog, OpenAI-compatible LLM config/client.

---

Implementation is tracked in this conversation; the final backend must pass backend unittest, existing Node frontend tests, compile checks, and API smoke.
