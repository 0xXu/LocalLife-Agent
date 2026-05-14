# Agent Architecture Upgrade Design

> Upgrading RankerAgent, ValidatorAgent, RecoveryAgent from single LLM-call functions to true ReAct agents with tool calling, memory, and autonomous reasoning.

## Goals

1. **Prepare for real APIs** — agents can autonomously explore dynamic data sources
2. **Improve recommendation quality** — multi-step reasoning with tool-augmented evidence gathering
3. **Correct architecture** — align with industry-standard agent patterns (ReAct loop, tool calling, memory)

## Non-Goals

- Writing side-effect tools (booking, payment) stay in pipeline confirmation node
- Agent-to-agent communication (no agent spawns another agent)
- Code agents (agents write code) — tool calling only

---

## 1. Agent Subgraph Structure

Each agent becomes a LangGraph subgraph using `create_react_agent`:

```
START → agent_node (LLM + bound tools) → conditional routing
    ├─ has tool_calls → ToolNode → agent_node (loop)
    └─ no tool_calls → END
```

### Factory Pattern

```python
def build_react_agent(llm, tools, prompt, checkpointer=None):
    """Wrap create_react_agent for future migration to create_agent."""
    return create_react_agent(
        llm,
        tools=tools,
        prompt=prompt,
        checkpointer=checkpointer,
    )
```

System prompt passed via `prompt=` parameter. Messages input contains only user message.

### Per-Agent Toolsets

| Agent | Tools | Purpose |
|-------|-------|---------|
| RankerAgent | search_places, get_poi_details, check_availability, compare_pois | Explore candidates, compare, select top N |
| ValidatorAgent | check_weather, check_opening_hours, check_availability, check_route_time | Verify plan feasibility step by step |
| RecoveryAgent | search_alternatives, check_availability, compare_options, estimate_cost | Find and evaluate replacement options |

### Agent Prompts (Responsibility Boundaries)

Each agent has an independent system prompt with clear scope:

- **RankerAgent**: Discover and rank candidate POIs. Do not validate full itinerary feasibility.
- **ValidatorAgent**: Verify feasibility of an existing plan. Do not search for alternatives.
- **RecoveryAgent**: Find substitutes when the original plan fails. Compare by availability, cost, distance.

### Adapter Layer

Subgraph runs ReAct internally (messages). Adapter converts final output to business fields:

```python
def ranker_agent_node(state):
    try:
        result = ranker_graph.invoke(input, config)
        output = parse_ranker_output(result["messages"][-1].content, candidates)
    except GraphRecursionError:
        output = deterministic_fallback(candidates)
        output["warnings"] = [{"code": "RANKER_AGENT_RECURSION_LIMIT"}]
    except Exception:
        output = deterministic_fallback(candidates)
        output["warnings"] = [{"code": "RANKER_AGENT_FAILED"}]
    return output
```

Output must match current pipeline contract (`ranked` dict / `validation` dict / `recovery_decision` dict).

---

## 2. Memory Architecture

### Short-Term Memory (Task-Scoped)

- **messages**: ReAct conversation history within one agent invocation (ephemeral)
- **checkpointer + thread_id**: For task recovery, debug, human-in-the-loop pause/resume (recoverable)
- **working_memory**: Structured task-level state (key findings, intermediate decisions)

**working_memory lifecycle:**
- Injected into dynamic system prompt before agent invocation
- Extracted from messages/final output by adapter after agent invocation
- First version: run-level (not step-level). Future: expand to step-level by replacing `create_react_agent` with explicit StateGraph.

**working_memory injection:** Embedded in system prompt, NOT as extra user message.

```python
def build_ranker_prompt(working_memory, long_term_prefs):
    return f"""You are RankerAgent.
...
Current working memory:
{json.dumps(working_memory, ensure_ascii=False, indent=2)}
"""
```

### Long-Term Memory (Cross-Request)

Uses `BaseStore` with namespace-separated keys:

```
("users", user_id, "preferences")      → explicit preferences
("users", user_id, "recommendation_history")  → past choices/rejections
("users", user_id, "constraints")       → learned constraints
("pois", poi_id, "feedback")            → user feedback on POI
("pois", poi_id, "operational_notes")   → operational knowledge
("agents", agent_id, "learned_rules")   → agent-level learned patterns
```

**Selective retrieval:** Only fetch relevant memories for the current task. Do NOT dump all history into prompt.

```python
preferences = store.get(("users", user_id, "preferences"), "profile")
history = store.search(("users", user_id, "recommendation_history"), limit=20)
```

**Memory item schema:**

```python
class MemoryItem(BaseModel):
    type: Literal["preference", "history", "poi_feedback"]
    content: dict
    source: Literal["user_explicit", "user_behavior", "agent_inferred", "system_observed"]
    confidence: float
    created_at: str
    updated_at: str
    expires_at: str | None = None
```

**Write policy:**
- Agents do NOT write long-term memory directly
- Pipeline writes after confirmation node
- User-explicit preferences → hard memory (direct write)
- Behavioral inference → soft memory with source + confidence; upgrade to preference after multiple evidence

---

## 3. Tool Design

### Pydantic Args Schema

Every tool uses `BaseModel` for input schema:

```python
class SearchPlacesInput(BaseModel):
    scenario: str = Field(description="Scenario label, e.g. 'family', 'date', 'hiking'")
    radius_km: float = Field(description="Search radius in kilometers", ge=0.5, le=20)
    tags: list[str] = Field(description="Filter tags, e.g. ['child_friendly', 'indoor']")

@tool(args_schema=SearchPlacesInput)
def search_places(scenario: str, radius_km: float, tags: list[str]) -> dict:
    """Search candidate POIs matching the scenario, radius, and tags."""
    ...
```

### Factory Pattern

Tools created per-request via factory, not global functions:

```python
def build_ranker_tools(registry: LocalToolRegistry, context: AgentContext):
    @tool(args_schema=SearchPlacesInput)
    def search_places(scenario: str, radius_km: float, tags: list[str]) -> dict:
        """Search candidate POIs."""
        return registry.search_places(scenario, radius_km, tags, user_id=context.user_id)

    @tool(args_schema=GetPoiDetailsInput)
    def get_poi_details(poi_id: str) -> dict:
        """Get detailed information for one POI."""
        return registry.get_poi_details(poi_id, user_id=context.user_id)

    return [search_places, get_poi_details, check_availability, compare_pois]
```

### Internal Context Not Exposed

user_id, trace_id, auth_token, store, registry injected via closure. LLM only sees business parameters.

### Shared Tools with Per-Agent Descriptions

Same underlying implementation, different descriptions per agent:

- **RankerAgent**: "Check whether a POI has enough availability for rough ranking."
- **ValidatorAgent**: "Strictly verify whether the selected POI is available at the exact planned time."
- **RecoveryAgent**: "Check availability for replacement POIs before proposing them."

### Unified Return Envelope

```python
# Success
{"ok": True, "data": {...}, "warnings": [], "source": "local_catalog", "fetched_at": "2026-05-14T..."}

# Business failure (not exception)
{"ok": False, "error_code": "POI_NOT_FOUND", "message": "No POI found for poi_id=..."}
```

Business failures returned as structured results, not exceptions. LLM handles them naturally.

### Read-Only by Default

RankerAgent / ValidatorAgent / RecoveryAgent tools are read-only: search, compare, check, estimate.

Writing tools (reserve, order, pay, write_memory) stay in pipeline confirmation node, require user confirmation.

---

## 4. Pipeline Integration

### Graph Topology Unchanged

```
parse_intent → build_context → [search_activities, search_restaurants, search_walks] → merge
→ ranker_agent → build_itinerary → validator_agent → (confirm | recovery → ranker_agent)
→ prepare_confirmation → END
```

Only the internals of three agent nodes change. Downstream nodes unaffected.

### Checkpointer

Managed by parent pipeline graph, not per-subgraph:

```python
checkpointer = InMemorySaver()  # or SQLite/Postgres in production
store = InMemoryStore()          # for long-term memory

pipeline_graph = pipeline_builder.compile(
    checkpointer=checkpointer,
    store=store,
)

config = {
    "configurable": {
        "thread_id": plan_id,
        "user_id": user_id,
    },
    "recursion_limit": 12,
}

result = pipeline_graph.invoke(initial_state, config=config)
```

Config passed down to subgraph invocations.

### Agent Subgraph Persistence Mode

Per-invocation (first version): each rank/validate/recover call is fresh. No cross-request message accumulation.

Long-term memory managed by BaseStore. Agent messages do not need to persist across requests.

---

## 5. Error Handling & Observability

### Error Handling by Agent Type

**RankerAgent failure** → Degraded fallback. Pipeline continues with deterministic ranking.

```python
{
    "ranked": deterministic_fallback(candidates),
    "warnings": [{"code": "RANKER_AGENT_FAILED"}]
}
```

**ValidatorAgent failure** → Cannot silently pass. Routes to recovery or manual confirmation.

```python
{
    "validation_status": "unknown",
    "safe_to_confirm": False,
    "warnings": [{"code": "VALIDATOR_AGENT_FAILED"}]
}
```

**RecoveryAgent failure** → Cannot fabricate alternatives. Returns requires_user_confirmation.

```python
{
    "recovery_status": "failed",
    "alternatives": [],
    "requires_user_confirmation": True
}
```

### Max Steps via recursion_limit

LangGraph's `recursion_limit` in config. Catch `GraphRecursionError`:

```python
config = {"recursion_limit": 12, ...}
try:
    result = graph.invoke(input, config)
except GraphRecursionError:
    result = fallback_with_warning("AGENT_RECURSION_LIMIT_REACHED")
```

### Progress Events

Human-readable status, NOT raw reasoning:

```json
{
    "type": "agent_progress",
    "agent": "ValidatorAgent",
    "phase": "tool_call",
    "message": "Checking opening hours",
    "tool_name": "check_opening_hours",
    "status": "running"
}
```

Do NOT expose: raw LLM reasoning, full tool args, user privacy data, auth context, raw POI data.

### Trace from Streaming Events

Prefer LangGraph stream events over post-hoc message parsing:

```python
for event in ranker_graph.stream(input, config, stream_mode="events"):
    if event["event"] == "on_tool_start":
        emit_trace(tool_call_event(event))
    elif event["event"] == "on_tool_end":
        emit_trace(tool_result_event(event))
```

Messages parsing as audit fallback.

### Trace Schema

```python
{
    "trace_id": str,
    "plan_id": str,
    "thread_id": str,
    "agent": "RankerAgent",
    "node": "tools",
    "event_type": "tool_call | tool_result | llm_start | llm_end | error",
    "tool_name": "check_availability",
    "tool_call_id": str,
    "status": "ok | error | fallback",
    "input_summary": dict,
    "output_summary": dict,
    "duration_ms": int,
    "token_usage": dict,
    "error_code": str | None,
}
```

---

## File Changes (Expected)

| File | Action | Description |
|------|--------|-------------|
| `backend/agents/base.py` | Modify | Add ReAct agent factory, tool binding, memory injection |
| `backend/agents/ranker.py` | Modify | Convert to ReAct subgraph with tools |
| `backend/agents/validator.py` | Modify | Convert to ReAct subgraph with tools |
| `backend/agents/recovery.py` | Modify | Convert to ReAct subgraph with tools |
| `backend/agents/tools.py` | Create | Tool definitions with Pydantic schemas, factory functions |
| `backend/agents/memory.py` | Create | Memory item schema, store integration, selective retrieval |
| `backend/orchestrator/pipeline.py` | Modify | Agent node adapters, checkpointer config, progress events |
| `backend/agents/__init__.py` | Modify | Update exports |
| `tests/backend/test_agents.py` | Modify | Update for new agent interfaces |
| `tests/backend/test_react_agents.py` | Create | ReAct loop tests, tool calling tests, memory tests |
