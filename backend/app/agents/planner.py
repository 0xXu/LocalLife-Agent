"""Single OpenAI Agents SDK route-planning agent."""

from typing import Protocol

from agents import Agent

from .tools import RouteTools


class RouteAgentRunner(Protocol):
    """Injectable boundary for executing the route agent in HTTP handlers."""

    async def run(self, *, query: str, city: str, user_id: str) -> object: ...


ROUTE_PLANNER_INSTRUCTIONS = """You plan local routes by calling the provided tools.
Never invent POIs, prices, ratings, travel times, constraints, or availability.
Use parse_intent and search_pois to ground requests in returned data. Generate,
check, score, and explain routes through the tools. deterministic constraint
validation is authoritative: do not present a route as feasible unless the
constraint tool reports it valid. Do not claim that data was saved; these tools
are read-only. If no validated route exists, say so plainly and request a
constraint change. Return factual summaries based only on tool outputs.
"""


def build_route_agent(tools: RouteTools) -> Agent[None]:
    """Build the one tool-using agent for route planning; no agent handoffs."""

    return Agent(
        name="route_planner",
        instructions=ROUTE_PLANNER_INSTRUCTIONS,
        tools=list(tools.sdk_tools),
    )
